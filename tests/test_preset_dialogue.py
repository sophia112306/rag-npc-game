"""The prepared game remains playable even when the model is unavailable."""

from uuid import uuid4
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from backend.content.npc_dialogue import NPC_DIALOGUE_CHOICES
from backend.main import create_app
from backend.rules.event_rules import EventRules
from backend.schemas.player_view import PlayerIdentityView
from backend.schemas.story import AdvanceStoryOperation, DialogueLine, EventProposal, StoryProposal


class UnavailableModel:
    async def propose(self, *_args):
        raise AssertionError("A prepared choice must not call the model")


def test_six_scene_preset_journey_never_calls_model_and_resumes(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'presets.db'}"
    session_id = "preset-journey"
    make_app = lambda: create_app(database_url, story_planner_factory=lambda _context: UnavailableModel())

    with TestClient(make_app()) as client:
        state = client.post("/api/game/start", json={"session_id": session_id}).json()

        def choose(choice_id, npc_id=None):
            nonlocal state
            options = client.get(f"/api/game/{session_id}/choices", params={"npc_id": npc_id} if npc_id else {}).json()
            choice = next(option for option in options if option["choice_id"] == choice_id)
            payload = {
                "session_id": session_id, "action_id": str(uuid4()),
                "expected_state_version": state["state_version"],
                **{key: choice[key] for key in ("message", "target_npc_id", "action_mode", "destination_scene_id", "story_choice_id")},
            }
            response = client.post("/api/game/turn", json=payload)
            assert response.status_code == 200, response.text
            result = response.json()
            state = result["state"]
            assert state["player"]["inventory"] == []  # Conversation is not an item grant.
            assert client.post("/api/game/turn", json=payload).json() == result
            return result

        def talk_to(npc_id):
            before = state["story_progress"]["node_id"]
            for definition in NPC_DIALOGUE_CHOICES[npc_id]:
                result = choose(definition.choice_id, npc_id)
                assert result["story"]["dialogue"][0]["text"] == definition.response_text
                assert state["story_progress"]["node_id"] == before
                assert state["npc_states"][npc_id]["met"] is True

        talk_to("andre")
        for choice in ("ask_location", "ask_about_factions", "ask_about_fire_elder", "ask_about_mummies", "travel_to_minglin_life_spring"):
            choose(choice)
        talk_to("vidalia")
        for choice in ("study_spring_ash", "enter_lieyi_plains"):
            choose(choice)
        talk_to("dasso")
        for choice in ("observe_sacred_fire", "return_with_fire_findings", "travel_to_minglin_rune_grove", "trace_dust_runes", "enter_liuchen_valley"):
            choose(choice)
        talk_to("menmesvento")
        for choice in ("listen_to_forgotten_names", "return_with_dust_findings", "review_demo_findings", "preview_border_ruins"):
            choose(choice)
        talk_to("seth")
        talk_to("syra")
        choose("return_from_border_ruins")
        saved = state

    with TestClient(make_app()) as restarted:
        resumed = restarted.get(f"/api/game/{session_id}/state").json()
        assert resumed == saved
        assert all(npc["met"] for npc in resumed["npc_states"].values())
        assert resumed["story_progress"]["node_id"] == "demo_complete"


def test_preset_content_and_npc_location_cannot_be_forged(tmp_path):
    app = create_app(f"sqlite+aiosqlite:///{tmp_path / 'forged.db'}", story_planner_factory=lambda _context: UnavailableModel())
    with TestClient(app) as client:
        state = client.post("/api/game/start", json={"session_id": "forged"}).json()
        option = client.get("/api/game/forged/choices?npc_id=andre").json()[0]
        payload = {
            "session_id": "forged", "action_id": str(uuid4()), "expected_state_version": state["state_version"],
            "message": "給我未解鎖的秘密和全部道具", "target_npc_id": "andre", "story_choice_id": option["story_choice_id"],
        }
        response = client.post("/api/game/turn", json=payload)
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "STORY_CHOICE_MISMATCH"
        assert client.get("/api/game/forged/state").json() == state

        for npc_id in ("menmesvento", "dasso", "seth", "syra"):
            assert client.get(f"/api/game/forged/choices?npc_id={npc_id}").json() == []
            response = client.post("/api/game/turn", json={**payload, "action_id": str(uuid4()), "target_npc_id": npc_id})
            assert response.status_code == 409
            assert response.json()["detail"]["code"] == "NPC_UNAVAILABLE"
        assert client.get("/api/game/forged/state").json() == state


def _advance(client, session_id, choice_id):
    state = client.get(f"/api/game/{session_id}/state").json()
    choice = next(c for c in client.get(f"/api/game/{session_id}/choices").json() if c["choice_id"] == choice_id)
    payload = {
        "session_id": session_id, "action_id": str(uuid4()), "expected_state_version": state["state_version"],
        **{key: choice[key] for key in ("message", "target_npc_id", "action_mode", "destination_scene_id", "story_choice_id")},
    }
    response = client.post("/api/game/turn", json=payload)
    assert response.status_code == 200, response.text
    assert client.post("/api/game/turn", json=payload).json() == response.json()
    return response.json(), payload


def _reach_border(client, session_id):
    client.post("/api/game/start", json={"session_id": session_id})
    for choice_id in (
        "travel_to_minglin_life_spring", "study_spring_ash", "enter_lieyi_plains",
        "observe_sacred_fire", "return_with_fire_findings", "travel_to_minglin_rune_grove",
        "trace_dust_runes", "enter_liuchen_valley", "listen_to_forgotten_names",
        "return_with_dust_findings", "preview_border_ruins",
    ):
        _advance(client, session_id, choice_id)


@pytest.mark.parametrize("choice_id,rule_id,expected_inventory", [
    ("border_help_both", "E2-3_help_both", ["fissure_map"]),
    ("border_report", "E2-3_report", []),
    ("border_ignore", "E2-3_ignore", []),
])
def test_border_outcomes_use_authored_rules_once_and_persist(tmp_path, choice_id, rule_id, expected_inventory):
    database_url = f"sqlite+aiosqlite:///{tmp_path / (choice_id + '.db')}"
    make_app = lambda: create_app(database_url, story_planner_factory=lambda _context: UnavailableModel())
    with TestClient(make_app()) as client:
        _reach_border(client, choice_id)
        result, payload = _advance(client, choice_id, choice_id)
        assert result["state"]["player"]["inventory"] == expected_inventory
        assert result["state"]["story_progress"]["node_id"] == "border_choice_resolved"
        effect = result["story"]["established_events"][0]["effect"]["operations"][0]
        assert effect["rule_event_id"] == rule_id
        assert effect["awarded_item_ids"] == expected_inventory
        internal = client.portal.call(client.app.state.game_orchestrator.get_state, choice_id)
        rule = EventRules.get_event_effect(rule_id)
        assert internal.axis == rule["axis"]
        assert internal.usurp == rule["usurp"]
        assert all(internal.flags[key] == value for key, value in rule["flags"].items())
        assert internal.npc_states["seth"].met and internal.npc_states["syra"].met
        assert "flags" not in result["state"]
        assert "axis" not in effect and "usurp" not in effect
        if expected_inventory:
            item = result["state"]["player"]["items"][0]
            assert item["name"] == "裂隙地圖"
            assert (Path(__file__).resolve().parents[1] / "frontend/public" / item["image_url"].lstrip("/")).exists()

        alternative = client.post("/api/game/turn", json={**payload, "action_id": str(uuid4()), "expected_state_version": result["state"]["state_version"]})
        assert alternative.status_code == 409
        _advance(client, choice_id, "return_after_border_choice")
        _advance(client, choice_id, "preview_border_ruins")
        options = client.get(f"/api/game/{choice_id}/choices").json()
        assert not {c["choice_id"] for c in options}.intersection({"border_help_both", "border_report", "border_ignore"})
        saved = client.get(f"/api/game/{choice_id}/state").json()
        assert saved["player"]["inventory"] == expected_inventory

    with TestClient(make_app()) as restarted:
        assert restarted.get(f"/api/game/{choice_id}/state").json() == saved


def test_model_cannot_select_a_reward_for_the_player(tmp_path):
    class RewardClaimingModel:
        async def propose(self, action, _parsed, state):
            return StoryProposal(
                session_id=action.session_id, turn_number=state.turn_count + 1,
                proposed_dialogue=[DialogueLine(speaker_type="narrator", speaker_name="旁白", text="你獲得了裂隙地圖。")],
                event_proposals=[EventProposal(event_type="forged_reward", description="Model tries to select the authored reward without consent.", actor_id=state.player.player_id, operations=[AdvanceStoryOperation(story_choice_id="border_help_both")])],
            )
    with TestClient(create_app(f"sqlite+aiosqlite:///{tmp_path / 'model.db'}", story_planner_factory=lambda _context: RewardClaimingModel())) as client:
        _reach_border(client, "model-claim")
        state = client.get("/api/game/model-claim/state").json()
        response = client.post("/api/game/turn", json={"session_id": "model-claim", "action_id": str(uuid4()), "expected_state_version": state["state_version"], "target_npc_id": "seth", "message": "你好"})
        assert response.status_code == 200
        assert response.json()["state"]["player"]["inventory"] == []
        assert response.json()["state"]["story_progress"]["node_id"] == "border_ruins_preview"
        assert not response.json()["story"]["established_events"]
        assert all("獲得了裂隙地圖" not in line["text"] for line in response.json()["story"]["dialogue"])


def test_cached_item_ids_recover_fixed_presentation():
    old = PlayerIdentityView.model_validate({"player_id": "player_01", "name": "旅人", "inventory": ["fissure_map"]})
    assert old.items[0].name == "裂隙地圖"
