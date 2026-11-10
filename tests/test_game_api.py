"""M1 API contract tests for the existing frontend integration."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.generation.planner import GatewayStoryPlanner, StoryGenerationUnavailableError
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


def test_default_capabilities_identify_rule_based_generation(client: TestClient) -> None:
    response = client.get("/api/capabilities")

    assert response.status_code == 200
    assert response.json() == {
        "generation_mode": "rule_based",
        "dynamic_dialogue": True,
        "rag_integration": "pending",
        "voice_integration": "pending",
        "allowed_operations": [
            "transfer_item",
            "establish_commitment",
            "offer_quest",
            "change_scene",
        ],
    }


def test_start_turn_and_read_current_state(client: TestClient) -> None:
    state = start_session(client)
    choices = client.get(f"/api/game/{state['session_id']}/choices")

    assert state["turn_count"] == 0
    assert state["state_version"] == 1
    assert state["current_scene_id"] == "minglin"
    assert state["current_scene"]["display_name"] == "平衡議會"
    assert state["current_scene"]["background_url"] == "/game/forest-council.png"
    assert state["story_progress"] == {
        "arc_id": "vita_anomaly_demo_v1",
        "node_id": "minglin_arrival",
        "chapter_title": "鳴霖異象",
        "mode": "demo_fallback",
        "public_clue_ids": [],
    }
    assert state["npc_states"]["vidalia"]["met"] is True
    assert "truth_level" not in state
    assert "axis" not in state
    assert "usurp" not in state
    assert "flags" not in state
    assert "relation" not in state["npc_states"]["vidalia"]
    assert choices.status_code == 200
    assert [choice["choice_id"] for choice in choices.json()] == [
        "ask_location",
        "ask_for_task",
        "travel_to_minglin_life_spring",
        "travel_to_minglin_rune_grove",
    ]
    assert all(
        choice["target_npc_id"] == "vidalia"
        for choice in choices.json()[:2]
    )
    assert all(
        choice["action_mode"] == "movement"
        and choice["target_npc_id"] is None
        and choice["destination_scene_id"]
        for choice in choices.json()[2:]
    )

    response = client.post("/api/game/turn", json=action_payload(state["session_id"]))

    assert response.status_code == 200
    turn = response.json()
    assert turn["turn_number"] == 1
    assert turn["state"]["turn_count"] == 1
    assert turn["state"]["state_version"] == 2
    assert "truth_level" not in turn["state"]
    assert "flags" not in turn["state"]
    assert turn["parsed_action"]["action_type"] == "dialogue"
    assert "你好，旅人" in turn["story"]["dialogue"][0]["text"]
    assert "開發替身" not in turn["story"]["dialogue"][0]["text"]
    assert turn["story"]["established_events"] == []
    assert "proposal_decisions" not in turn

    state_response = client.get(f"/api/game/{state['session_id']}/state")
    assert state_response.status_code == 200
    assert state_response.json()["state_version"] == 2
    assert "truth_level" not in state_response.json()
    assert "flags" not in state_response.json()


def test_default_rule_planner_offers_and_remembers_dynamic_quest(client: TestClient) -> None:
    state = start_session(client, "rule-quest-session")
    first = client.post(
        "/api/game/turn",
        json={
            **action_payload(state["session_id"]),
            "message": "有什麼需要我幫忙的任務？",
        },
    )
    quests = client.get(f"/api/game/{state['session_id']}/quests")
    choices = client.get(f"/api/game/{state['session_id']}/choices")
    second = client.post(
        "/api/game/turn",
        json={
            **action_payload(state["session_id"], expected_state_version=2),
            "message": "請再告訴我任務內容",
        },
    )
    quests_after_second_turn = client.get(f"/api/game/{state['session_id']}/quests")

    assert first.status_code == 200
    system_line = first.json()["story"]["dialogue"][1]
    assert system_line["speaker_name"] == "系統"
    assert "維達利亞" in system_line["text"]
    assert "玩家" in system_line["text"]
    assert state["session_id"] not in system_line["text"]
    assert quests.status_code == 200
    assert len(quests.json()) == 1
    assert quests.json()[0]["status"] == "offered"
    assert "鳴霖・平衡議會" in quests.json()[0]["title"]
    assert choices.status_code == 200
    assert [choice["choice_id"] for choice in choices.json()] == [
        "ask_current_quest",
        "promise_to_report",
        "travel_to_minglin_life_spring",
        "travel_to_minglin_rune_grove",
    ]
    assert quests.json()[0]["title"] in choices.json()[0]["label"]
    assert second.status_code == 200
    assert quests.json()[0]["title"] in second.json()["story"]["dialogue"][0]["text"]
    assert len(quests_after_second_turn.json()) == 1


def test_choices_for_unknown_session_return_not_found(client: TestClient) -> None:
    response = client.get("/api/game/missing-session/choices")

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "SESSION_NOT_FOUND"


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


def test_generation_failure_returns_503_without_committing_turn(tmp_path) -> None:
    class FailingPlanner:
        async def propose(self, action, parsed_action, state):
            raise StoryGenerationUnavailableError("model_timeout", 2)

    application = create_app(
        f"sqlite+aiosqlite:///{tmp_path / 'model-failure.db'}",
        story_planner_factory=lambda _context: FailingPlanner(),
    )
    with TestClient(application) as failing_client:
        state = start_session(failing_client, "model-failure-session")
        failed = failing_client.post(
            "/api/game/turn",
            json=action_payload(state["session_id"]),
        )
        unchanged = failing_client.get(f"/api/game/{state['session_id']}/state")

    assert failed.status_code == 503
    assert failed.headers["retry-after"] == "2"
    assert failed.json()["detail"] == {
        "code": "STORY_GENERATION_UNAVAILABLE",
        "message": "Story generation is temporarily unavailable",
        "reason": "model_timeout",
        "attempts": 2,
    }
    assert unchanged.status_code == 200
    assert unchanged.json()["turn_count"] == 0
    assert unchanged.json()["state_version"] == 1


def test_configured_gateway_dialogue_reaches_player_after_validation(tmp_path) -> None:
    class DynamicGateway:
        async def generate_story(self, request):
            return {
                "intent_summary": "Respond to the player's greeting.",
                "npc_dialogue": [
                    {
                        "text": "旅人，我記得你剛才的問候；命脈之泉仍在等待答案。",
                        "emotion": "thoughtful",
                    }
                ],
                "event_proposals": [],
            }

    application = create_app(
        f"sqlite+aiosqlite:///{tmp_path / 'dynamic-model.db'}",
        story_planner_factory=lambda context: GatewayStoryPlanner(DynamicGateway(), context),
    )
    with TestClient(application) as dynamic_client:
        state = start_session(dynamic_client, "dynamic-model-session")
        capabilities = dynamic_client.get("/api/capabilities")
        response = dynamic_client.post(
            "/api/game/turn",
            json=action_payload(state["session_id"]),
        )

    assert response.status_code == 200
    assert capabilities.json()["generation_mode"] == "external_model"
    assert capabilities.json()["dynamic_dialogue"] is True
    line = response.json()["story"]["dialogue"][0]
    assert line["speaker_id"] == "vidalia"
    assert line["speaker_name"] == "維達利亞"
    assert "命脈之泉" in line["text"]
    assert "開發替身" not in line["text"]


def test_next_model_turn_receives_committed_memory_and_commitment(tmp_path) -> None:
    class ContinuityGateway:
        def __init__(self) -> None:
            self.requests = []

        async def generate_story(self, request):
            self.requests.append(request)
            if request.turn_number == 1:
                return {
                    "intent_summary": "Record the player's explicit promise.",
                    "npc_dialogue": [{"text": "我會記得你的承諾。"}],
                    "event_proposals": [
                        {
                            "event_type": "commitment_created",
                            "description": "Untrusted wording.",
                            "actor_id": request.player_id,
                            "target_id": request.target_context.npc_id,
                            "operations": [
                                {
                                    "operation_type": "establish_commitment",
                                    "summary": "玩家答應帶回地圖碎片。",
                                    "promisor_id": request.player_id,
                                    "promisee_id": request.target_context.npc_id,
                                    "due_in_turns": 3,
                                }
                            ],
                            "witness_ids": [request.player_id, request.target_context.npc_id],
                            "visible_to_player": True,
                        }
                    ],
                }
            return {
                "intent_summary": "Continue from persisted context.",
                "npc_dialogue": [{"text": "你的承諾仍未完成。"}],
                "event_proposals": [],
            }

    gateway = ContinuityGateway()
    application = create_app(
        f"sqlite+aiosqlite:///{tmp_path / 'continuity.db'}",
        story_planner_factory=lambda context: GatewayStoryPlanner(gateway, context),
    )
    with TestClient(application) as continuity_client:
        state = start_session(continuity_client, "continuity-session")
        first = continuity_client.post(
            "/api/game/turn",
            json={
                **action_payload(state["session_id"]),
                "message": "我答應帶回地圖碎片",
            },
        )
        second = continuity_client.post(
            "/api/game/turn",
            json={
                **action_payload(state["session_id"], expected_state_version=2),
                "message": "你還記得嗎？",
            },
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(gateway.requests) == 2
    next_context = gateway.requests[1].target_context
    assert [item.summary for item in next_context.active_commitments] == [
        "玩家答應帶回地圖碎片。"
    ]
    assert {memory.memory_type for memory in next_context.memories} == {
        "interaction",
        "observed_event",
    }
    assert any("我答應帶回地圖碎片" in memory.content for memory in next_context.memories)


def test_dynamic_quest_is_offered_persisted_and_carried_forward(tmp_path) -> None:
    class QuestGateway:
        def __init__(self) -> None:
            self.requests = []

        async def generate_story(self, request):
            self.requests.append(request)
            if request.turn_number == 1:
                return {
                    "intent_summary": "Offer a generated quest without auto-accepting it.",
                    "npc_dialogue": [{"text": "你願意替我找回泉邊的地圖碎片嗎？"}],
                    "event_proposals": [
                        {
                            "event_type": "quest_offered",
                            "description": "Untrusted quest wording.",
                            "actor_id": request.target_context.npc_id,
                            "target_id": request.player_id,
                            "operations": [
                                {
                                    "operation_type": "offer_quest",
                                    "title": "尋回地圖碎片",
                                    "summary": "調查泉邊並帶回已確認存在的地圖碎片。",
                                    "giver_id": request.target_context.npc_id,
                                    "recipient_id": request.player_id,
                                    "due_in_turns": 5,
                                }
                            ],
                            "witness_ids": [request.player_id, request.target_context.npc_id],
                            "visible_to_player": True,
                        }
                    ],
                }
            return {
                "intent_summary": "Remember the open quest.",
                "npc_dialogue": [{"text": "那項委託仍等著你的答覆。"}],
                "event_proposals": [],
            }

    gateway = QuestGateway()
    application = create_app(
        f"sqlite+aiosqlite:///{tmp_path / 'quest.db'}",
        story_planner_factory=lambda context: GatewayStoryPlanner(gateway, context),
    )
    with TestClient(application) as quest_client:
        state = start_session(quest_client, "quest-session")
        first = quest_client.post(
            "/api/game/turn",
            json={**action_payload(state["session_id"]), "message": "有什麼需要幫忙？"},
        )
        quests = quest_client.get(f"/api/game/{state['session_id']}/quests")
        second = quest_client.post(
            "/api/game/turn",
            json={
                **action_payload(state["session_id"], expected_state_version=2),
                "message": "讓我想想。",
            },
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert quests.status_code == 200
    assert quests.json()[0]["title"] == "尋回地圖碎片"
    assert quests.json()[0]["status"] == "offered"
    assert [item.title for item in gateway.requests[1].target_context.active_quests] == [
        "尋回地圖碎片"
    ]
