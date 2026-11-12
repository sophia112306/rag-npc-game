"""Scene assets, travel rules, persistence, and API integration tests."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.content.scenes import SCENES
from backend.content.world_scenes import build_world_scene
from backend.main import create_app
from backend.rules.event_rules import EventRules
from backend.schemas.game_state import GameState


def test_scene_registry_references_existing_assets_and_destinations() -> None:
    public_root = Path("frontend/public")
    manifest = json.loads(
        (public_root / "game/scenes/manifest.json").read_text(encoding="utf-8")
    )
    generated_ids = {asset["scene_id"] for asset in manifest["assets"]}

    assert generated_ids == {
        "minglin_life_spring",
        "minglin_rune_grove",
        "liuchen_valley",
        "border_ruins",
        "lieyi_plains",
    }
    for scene in SCENES.values():
        assert (public_root / scene.background_url.removeprefix("/")).is_file()
        assert (public_root / scene.horizon_url.removeprefix("/")).is_file()
        assert scene.visual_profile.profile_id
        assert all(destination in SCENES for destination in scene.allowed_destinations)

    assert len(
        {scene.visual_profile.profile_id for scene in SCENES.values()}
    ) == len(SCENES)
    assert SCENES["liuchen_valley"].visual_profile.use_ground_texture is False
    assert SCENES["lieyi_plains"].visual_profile.liquid_color == "#ff681c"
    assert SCENES["minglin"].visual_profile.show_vidalia is True
    assert SCENES["minglin"].visual_profile.show_ground is False
    assert SCENES["minglin"].visual_profile.prop_groups == ()
    for story_scene_id in (
        "minglin_life_spring",
        "minglin_rune_grove",
        "liuchen_valley",
        "lieyi_plains",
    ):
        profile = SCENES[story_scene_id].visual_profile
        assert profile.show_vidalia is False
        assert profile.show_ground is False
        assert profile.prop_groups == ()

    for isolated_scene_id in ("liuchen_valley", "lieyi_plains"):
        assert all(
            isolated_scene_id not in scene.allowed_destinations
            for scene in SCENES.values()
        )


def test_3d_scene_contract_exposes_the_new_npcs_at_their_story_locations() -> None:
    """The Babylon client needs separately pickable characters in each region."""
    border = build_world_scene("border_ruins")
    plains = build_world_scene("lieyi_plains")
    valley = build_world_scene("liuchen_valley")

    assert {npc.npc_id for npc in border.npc_interactions} == {"seth", "syra"}
    assert {npc.npc_id for npc in plains.npc_interactions} == {"dasso"}
    assert valley.npc_id == "menmesvento"
    assert not valley.npc_interactions


def test_valid_scene_change_is_saved_and_resumed_after_restart(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'scene.db'}"
    session_id = "scene-persistence"
    action_id = str(uuid4())

    with TestClient(create_app(database_url)) as client:
        started = client.post("/api/game/start", json={"session_id": session_id}).json()
        choices = client.get(f"/api/game/{session_id}/choices").json()
        travel = next(
            choice
            for choice in choices
            if choice["destination_scene_id"] == "minglin_life_spring"
        )
        response = client.post(
            "/api/game/turn",
            json={
                "session_id": session_id,
                "action_id": action_id,
                "message": travel["message"],
                "input_type": "text",
                "target_npc_id": travel["target_npc_id"],
                "action_mode": travel["action_mode"],
                "destination_scene_id": travel["destination_scene_id"],
                "expected_state_version": started["state_version"],
            },
        )

        assert response.status_code == 200
        turn = response.json()
        assert turn["state"]["current_scene_id"] == "minglin_life_spring"
        assert turn["state"]["current_scene"]["display_name"] == "命脈之泉"
        assert turn["state"]["current_scene"]["background_url"].endswith(
            "minglin-life-spring-v1.png"
        )
        assert (
            turn["state"]["current_scene"]["visual_profile"]["profile_id"]
            == "minglin_life_spring"
        )
        operation = turn["story"]["established_events"][0]["effect"]["operations"][0]
        assert operation == {
            "operation_type": "change_scene",
            "source_scene_id": "minglin",
            "destination_scene_id": "minglin_life_spring",
        }

    with TestClient(create_app(database_url)) as client:
        resumed = client.post("/api/game/start", json={"session_id": session_id})
        choices = client.get(f"/api/game/{session_id}/choices")

        assert resumed.status_code == 201
        assert resumed.json()["current_scene_id"] == "minglin_life_spring"
        assert [choice["destination_scene_id"] for choice in choices.json() if choice["action_mode"] == "movement"] == ["minglin"]


def test_unconnected_scene_change_is_rejected_without_mutating_location(tmp_path) -> None:
    client = TestClient(create_app(f"sqlite+aiosqlite:///{tmp_path / 'invalid-scene.db'}"))
    with client:
        session_id = "invalid-scene"
        started = client.post("/api/game/start", json={"session_id": session_id}).json()
        first = client.post(
            "/api/game/turn",
            json={
                "session_id": session_id,
                "action_id": str(uuid4()),
                "message": "我前往命脈之泉。",
                "input_type": "text",
                "target_npc_id": None,
                "action_mode": "movement",
                "destination_scene_id": "minglin_life_spring",
                "expected_state_version": started["state_version"],
            },
        ).json()
        rejected = client.post(
            "/api/game/turn",
            json={
                "session_id": session_id,
                "action_id": str(uuid4()),
                "message": "我直接前往符石林。",
                "input_type": "text",
                "target_npc_id": None,
                "action_mode": "movement",
                "destination_scene_id": "minglin_rune_grove",
                "expected_state_version": first["state"]["state_version"],
            },
        )

        assert rejected.status_code == 200
        assert rejected.json()["state"]["current_scene_id"] == "minglin_life_spring"
        assert rejected.json()["story"]["established_events"] == []


@pytest.mark.parametrize(
    ("scene_id", "display_name"),
    (("liuchen_valley", "流塵谷"), ("lieyi_plains", "烈燚原")),
)
def test_isolated_story_scene_is_not_an_ordinary_travel_destination(
    tmp_path,
    scene_id: str,
    display_name: str,
) -> None:
    """A registered story scene must not become reachable merely by knowing its ID."""

    database_url = f"sqlite+aiosqlite:///{tmp_path / f'{scene_id}-boundary.db'}"
    session_id = f"{scene_id}-boundary"
    action_id = str(uuid4())

    with TestClient(create_app(database_url)) as client:
        started = client.post("/api/game/start", json={"session_id": session_id}).json()
        choices = client.get(f"/api/game/{session_id}/choices").json()
        payload = {
            "session_id": session_id,
            "action_id": action_id,
            "message": f"我直接前往{display_name}。",
            "input_type": "text",
            "target_npc_id": None,
            "action_mode": "movement",
            "destination_scene_id": scene_id,
            "expected_state_version": started["state_version"],
        }
        rejected = client.post("/api/game/turn", json=payload)
        replay = client.post("/api/game/turn", json=payload)

        assert all(
            choice["destination_scene_id"] != scene_id
            for choice in choices
        )
        assert rejected.status_code == 200
        assert rejected.json()["state"]["current_scene_id"] == "minglin"
        assert rejected.json()["story"]["established_events"] == []
        assert replay.status_code == 200
        assert replay.json() == rejected.json()

    with TestClient(create_app(database_url)) as restarted_client:
        resumed = restarted_client.post(
            "/api/game/start",
            json={"session_id": session_id},
        )

        assert resumed.status_code == 201
        assert resumed.json()["current_scene_id"] == "minglin"
        assert resumed.json()["state_version"] == 2


def test_e3_1_fissure_map_escape_condition_remains_distinct_from_travel_graph() -> None:
    """C's danger rule may recognize the map without granting a normal scene edge."""

    state = GameState(session_id="e3-1-map-boundary")
    state.flags["fissure_map"] = False

    escaped_without_map, _ = EventRules.evaluate_danger_event(state, "E3-1", {})
    state.flags["fissure_map"] = True
    escaped_with_map, reason = EventRules.evaluate_danger_event(state, "E3-1", {})

    assert escaped_without_map is False
    assert escaped_with_map is True
    assert "成功脫身" in reason
    assert all(
        "liuchen_valley" not in scene.allowed_destinations
        for scene in SCENES.values()
    )


def test_destination_is_part_of_idempotency_content(tmp_path) -> None:
    with TestClient(
        create_app(f"sqlite+aiosqlite:///{tmp_path / 'scene-digest.db'}")
    ) as client:
        session_id = "scene-digest"
        started = client.post("/api/game/start", json={"session_id": session_id}).json()
        action_id = str(uuid4())
        payload = {
            "session_id": session_id,
            "action_id": action_id,
            "message": "我要移動。",
            "input_type": "text",
            "target_npc_id": None,
            "action_mode": "movement",
            "destination_scene_id": "minglin_life_spring",
            "expected_state_version": started["state_version"],
        }

        first = client.post("/api/game/turn", json=payload)
        conflict = client.post(
            "/api/game/turn",
            json={**payload, "destination_scene_id": "minglin_rune_grove"},
        )

        assert first.status_code == 200
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "ACTION_ID_CONFLICT"
