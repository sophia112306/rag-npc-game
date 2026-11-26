"""Tests for the public next-step guidance sent to dynamic NPC dialogue."""

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.generation.planner import GatewayStoryPlanner
from backend.main import create_app
from backend.orchestration.player_choices import build_turn_guidance
from backend.schemas.game_state import GameState, PlayerState
from backend.schemas.player_action import ActionMode
from backend.schemas.player_choice import PlayerChoice


def test_turn_guidance_uses_only_player_visible_actions() -> None:
    state = GameState(
        session_id="guided-session",
        current_scene_id="minglin",
        player=PlayerState(player_id="player"),
        flags={"unrevealed_ending": True},
        truth_level=3,
    )
    choices = [
        PlayerChoice(
            choice_id="travel_to_minglin_life_spring",
            label="前往命脈之泉",
            message="我前往命脈之泉。",
            action_mode=ActionMode.MOVEMENT,
            destination_scene_id="minglin_life_spring",
        )
    ]

    guidance = build_turn_guidance(state, choices)

    assert guidance.scene_name == "平衡議會"
    assert guidance.available_actions[0].label == "前往命脈之泉"
    assert guidance.available_actions[0].destination_scene_id == "minglin_life_spring"
    serialized = guidance.model_dump_json()
    assert "unrevealed_ending" not in serialized
    assert "truth_level" not in serialized


def test_free_model_turn_receives_current_objective_and_legal_actions(tmp_path) -> None:
    class CapturingGateway:
        def __init__(self) -> None:
            self.requests = []

        async def generate_story(self, request):
            self.requests.append(request)
            return {
                "intent_summary": "Guide the player to one legal investigation.",
                "npc_dialogue": [
                    {
                        "text": "先前往命脈之泉，從泉眼留下的痕跡開始查起。",
                        "emotion": "focused",
                    }
                ],
                "event_proposals": [],
            }

    def submit_choice(client: TestClient, session_id: str, state: dict, choice_id: str) -> dict:
        choices = client.get(f"/api/game/{session_id}/choices").json()
        choice = next(item for item in choices if item["choice_id"] == choice_id)
        response = client.post(
            "/api/game/turn",
            json={
                "session_id": session_id,
                "action_id": str(uuid4()),
                "expected_state_version": state["state_version"],
                "message": choice["message"],
                "target_npc_id": choice["target_npc_id"],
                "action_mode": choice["action_mode"],
                "destination_scene_id": choice["destination_scene_id"],
                "story_choice_id": choice["story_choice_id"],
            },
        )
        assert response.status_code == 200, response.text
        return response.json()["state"]

    gateway = CapturingGateway()
    application = create_app(
        f"sqlite+aiosqlite:///{tmp_path / 'guidance.db'}",
        story_planner_factory=lambda context: GatewayStoryPlanner(gateway, context),
    )
    with TestClient(application) as client:
        session_id = "guidance-model-session"
        state = client.post("/api/game/start", json={"session_id": session_id}).json()
        state = submit_choice(client, session_id, state, "meet_andre")
        state = submit_choice(client, session_id, state, "walk_to_council")
        state = submit_choice(client, session_id, state, "meet_vidalia")
        state = submit_choice(client, session_id, state, "ask_for_task")
        response = client.post(
            "/api/game/turn",
            json={
                "session_id": session_id,
                "action_id": str(uuid4()),
                "expected_state_version": state["state_version"],
                "message": "我現在不知道該去哪裡、要做什麼。",
                "target_npc_id": "vidalia",
                "action_mode": "dialogue",
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["story"]["dialogue"][0]["text"].startswith("先前往命脈之泉")
    guidance = gateway.requests[0].turn_guidance
    assert guidance.scene_name == "平衡議會"
    assert "命脈之泉" in guidance.objective
    labels = [action.label for action in guidance.available_actions]
    assert "前往命脈之泉" in labels
    assert "前往符石林" in labels
    assert all(action.destination_scene_id != "liuchen_valley" for action in guidance.available_actions)
