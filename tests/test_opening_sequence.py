from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import create_app


def _submit_choice(client: TestClient, session_id: str, state: dict, choice_id: str) -> dict:
    choice = next(
        item
        for item in client.get(f"/api/game/{session_id}/choices").json()
        if item["choice_id"] == choice_id
    )
    response = client.post(
        "/api/game/turn",
        json={
            "session_id": session_id,
            "action_id": str(uuid4()),
            "message": choice["message"],
            "input_type": "text",
            "target_npc_id": choice["target_npc_id"],
            "action_mode": choice["action_mode"],
            "destination_scene_id": choice["destination_scene_id"],
            "story_choice_id": choice["story_choice_id"],
            "expected_state_version": state["state_version"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["state"]


def test_opening_starts_in_minglin_with_andre_then_reveals_vidalia(tmp_path) -> None:
    with TestClient(create_app(f"sqlite+aiosqlite:///{tmp_path / 'opening.db'}")) as client:
        session_id = "opening-sequence"
        state = client.post("/api/game/start", json={"session_id": session_id}).json()

        assert state["current_scene_id"] == "minglin"
        assert state["story_progress"]["node_id"] == "minglin_arrival"
        assert state["world_scene"]["npc_id"] == "andre"
        assert [choice["choice_id"] for choice in client.get(f"/api/game/{session_id}/choices").json()] == [
            "meet_andre"
        ]
        assert state["alan_hud"]["display_value"] == 0

        state = _submit_choice(client, session_id, state, "meet_andre")
        assert state["current_scene_id"] == "minglin"
        assert state["story_progress"]["node_id"] == "minglin_path_open"
        assert state["npc_states"]["andre"]["met"] is True
        assert state["world_scene"]["npc_id"] == "andre"
        assert [choice["choice_id"] for choice in client.get(f"/api/game/{session_id}/choices").json()] == [
            "walk_to_council"
        ]

        state = _submit_choice(client, session_id, state, "walk_to_council")
        assert state["world_scene"]["npc_id"] == "vidalia"
        assert [choice["choice_id"] for choice in client.get(f"/api/game/{session_id}/choices").json()] == [
            "meet_vidalia"
        ]

        state = _submit_choice(client, session_id, state, "meet_vidalia")
        assert state["story_progress"]["node_id"] == "minglin_orientation"
        assert state["npc_states"]["vidalia"]["met"] is True
        assert [choice["choice_id"] for choice in client.get(f"/api/game/{session_id}/choices").json()] == [
            "ask_for_task"
        ]

        state = _submit_choice(client, session_id, state, "ask_for_task")
        assert state["story_progress"]["node_id"] == "minglin_briefed"
        assert {
            "travel_to_minglin_life_spring",
            "travel_to_minglin_rune_grove",
        }.issubset({
            choice["choice_id"]
            for choice in client.get(f"/api/game/{session_id}/choices").json()
        })


def test_opening_rejects_free_form_skip_without_spending_a_turn(tmp_path) -> None:
    with TestClient(create_app(f"sqlite+aiosqlite:///{tmp_path / 'opening-gate.db'}")) as client:
        session_id = "opening-gate"
        state = client.post("/api/game/start", json={"session_id": session_id}).json()
        response = client.post(
            "/api/game/turn",
            json={
                "session_id": session_id,
                "action_id": str(uuid4()),
                "message": "我直接去命脈之泉調查。",
                "input_type": "text",
                "target_npc_id": None,
                "action_mode": "movement",
                "destination_scene_id": "minglin_life_spring",
                "expected_state_version": state["state_version"],
            },
        )

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "STORY_CHOICE_UNAVAILABLE"
        current = client.get(f"/api/game/{session_id}/state").json()
        assert current["current_scene_id"] == "minglin"
        assert current["state_version"] == state["state_version"]


def test_opening_allows_natural_dialogue_at_each_revealed_npc(tmp_path) -> None:
    with TestClient(create_app(f"sqlite+aiosqlite:///{tmp_path / 'opening-free-text.db'}")) as client:
        session_id = "opening-free-text"
        state = client.post("/api/game/start", json={"session_id": session_id}).json()

        def submit(message: str, target: str, current: dict) -> dict:
            response = client.post(
                "/api/game/turn",
                json={
                    "session_id": session_id,
                    "action_id": str(uuid4()),
                    "message": message,
                    "input_type": "text",
                    "target_npc_id": target,
                    "action_mode": "dialogue",
                    "expected_state_version": current["state_version"],
                },
            )
            assert response.status_code == 200, response.text
            return response.json()["state"]

        state = submit("我在鳴霖醒來，這裡發生了什麼？", "andre", state)
        assert state["story_progress"]["node_id"] == "minglin_path_open"
        state = _submit_choice(client, session_id, state, "walk_to_council")
        state = submit("我在屏障裂隙醒來，也看到裂縫似乎正在擴大。", "vidalia", state)
        assert state["story_progress"]["node_id"] == "minglin_orientation"

        state = submit("裂縫還在擴大，我想知道接下來能幫上什麼忙。", "vidalia", state)
        assert state["story_progress"]["node_id"] == "minglin_briefed"
