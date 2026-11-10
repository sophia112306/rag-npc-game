"""M1 API contract tests for the existing frontend integration."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app


@pytest.fixture
def client(tmp_path) -> TestClient:
    application = create_app(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    with TestClient(application) as test_client:
        yield test_client


def start_session(client: TestClient, session_id: str = "m1-session") -> dict:
    response = client.post("/api/game/start", json={"session_id": session_id})
    assert response.status_code == 201
    return response.json()


def action_payload(
    session_id: str,
    *,
    action_id: str | None = None,
    expected_state_version: int = 1,
) -> dict:
    return {
        "session_id": session_id,
        "action_id": action_id or str(uuid4()),
        "message": "你好，維達利亞",
        "input_type": "text",
        "target_npc_id": "vidalia",
        "action_mode": "dialogue",
        "expected_state_version": expected_state_version,
    }


def test_public_character_profile_is_available(client: TestClient) -> None:
    response = client.get("/api/characters/vidalia")

    assert response.status_code == 200
    assert response.json()["npc_id"] == "vidalia"
    assert "memory" not in response.json()
    assert "secrets" not in response.json()


def test_start_turn_and_read_current_state(client: TestClient) -> None:
    state = start_session(client)

    assert state["turn_count"] == 0
    assert state["state_version"] == 1
    assert state["current_scene_id"] == "minglin"
    assert state["npc_states"]["vidalia"]["met"] is True
    assert "truth_level" not in state
    assert "axis" not in state
    assert "usurp" not in state
    assert "flags" not in state
    assert "relation" not in state["npc_states"]["vidalia"]

    response = client.post("/api/game/turn", json=action_payload(state["session_id"]))

    assert response.status_code == 200
    turn = response.json()
    assert turn["turn_number"] == 1
    assert turn["state"]["turn_count"] == 1
    assert turn["state"]["state_version"] == 2
    assert "truth_level" not in turn["state"]
    assert "flags" not in turn["state"]
    assert turn["parsed_action"]["action_type"] == "dialogue"
    assert "開發替身" in turn["story"]["dialogue"][0]["text"]
    assert turn["story"]["established_events"] == []
    assert "proposal_decisions" not in turn

    state_response = client.get(f"/api/game/{state['session_id']}/state")
    assert state_response.status_code == 200
    assert state_response.json()["state_version"] == 2
    assert "truth_level" not in state_response.json()
    assert "flags" not in state_response.json()


def test_repeated_action_id_does_not_advance_the_turn_twice(client: TestClient) -> None:
    state = start_session(client, "idempotent-session")
    payload = action_payload(state["session_id"])

    first = client.post("/api/game/turn", json=payload)
    second = client.post("/api/game/turn", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert second.json()["state"]["turn_count"] == 1


def test_reused_action_id_with_different_content_returns_conflict(client: TestClient) -> None:
    state = start_session(client, "digest-conflict-session")
    payload = action_payload(state["session_id"])
    first = client.post("/api/game/turn", json=payload)
    assert first.status_code == 200

    changed_payload = {**payload, "message": "這是不同的內容"}
    conflict = client.post("/api/game/turn", json=changed_payload)

    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "ACTION_ID_CONFLICT"


def test_stale_state_version_returns_conflict(client: TestClient) -> None:
    state = start_session(client, "version-session")
    first = client.post("/api/game/turn", json=action_payload(state["session_id"]))
    assert first.status_code == 200

    stale = client.post(
        "/api/game/turn",
        json=action_payload(state["session_id"], expected_state_version=1),
    )

    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "STATE_VERSION_CONFLICT"
    assert stale.json()["detail"]["actual_state_version"] == 2


def test_local_frontend_origin_passes_cors_preflight(client: TestClient) -> None:
    response = client.options(
        "/api/game/start",
        headers={
            "Origin": "http://localhost:3200",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3200"


def test_session_and_idempotent_response_survive_app_restart(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'restart.db'}"
    payload = action_payload("restart-session")

    with TestClient(create_app(database_url)) as first_client:
        start_session(first_client, payload["session_id"])
        first_response = first_client.post("/api/game/turn", json=payload)
        assert first_response.status_code == 200
        expected_response = first_response.json()

    with TestClient(create_app(database_url)) as restarted_client:
        state = restarted_client.get(f"/api/game/{payload['session_id']}/state")
        replay = restarted_client.post("/api/game/turn", json=payload)

    assert state.status_code == 200
    assert state.json()["turn_count"] == 1
    assert state.json()["state_version"] == 2
    assert replay.status_code == 200
    assert replay.json() == expected_response
