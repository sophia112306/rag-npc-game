"""Scene assets, travel rules, persistence, and API integration tests."""

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.content.scenes import SCENES
from backend.main import create_app


def test_scene_registry_references_existing_assets_and_destinations() -> None:
    public_root = Path("frontend/public")
    manifest = json.loads(
        (public_root / "game/scenes/manifest.json").read_text(encoding="utf-8")
    )
    generated_ids = {asset["scene_id"] for asset in manifest["assets"]}

    assert generated_ids == {"minglin_life_spring", "minglin_rune_grove"}
    for scene in SCENES.values():
        assert (public_root / scene.background_url.removeprefix("/")).is_file()
        assert (public_root / scene.horizon_url.removeprefix("/")).is_file()
        assert all(destination in SCENES for destination in scene.allowed_destinations)


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
