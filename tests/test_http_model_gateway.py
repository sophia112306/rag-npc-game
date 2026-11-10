"""HTTP adapter and opt-in environment configuration tests."""

import json

import httpx
import pytest

from backend.generation.config import build_story_planner_from_env
from backend.generation.gateway import (
    ModelGatewayPermanentError,
    ModelGatewayTransientError,
    ModelTurnRequest,
)
from backend.generation.http_gateway import HttpModelGateway
from backend.schemas.content import NPCGenerationContext
from backend.schemas.parsed_action import ParsedAction


def make_request() -> ModelTurnRequest:
    return ModelTurnRequest(
        session_id="http-session",
        turn_number=1,
        state_version=1,
        current_scene_id="minglin",
        player_id="player",
        player_inventory=[],
        action_message="你好",
        action_mode="dialogue",
        parsed_action=ParsedAction(intent="dialogue"),
        target_context=NPCGenerationContext(
            npc_id="vidalia",
            setting_version=1,
            public_profile={"npc_id": "vidalia"},
            private_profile={},
            knowledge=[],
            memories=[],
            missing_data=["character_definition_incomplete"],
        ),
        allowed_operations=["transfer_item"],
    )


@pytest.mark.asyncio
async def test_http_gateway_posts_contract_json_with_optional_bearer_token() -> None:
    captured = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "intent_summary": "A valid response",
                "npc_dialogue": [{"text": "Dynamic response"}],
                "event_proposals": [],
            },
        )

    gateway = HttpModelGateway(
        "https://model.example/generate",
        api_key="test-token",
        transport=httpx.MockTransport(handler),
    )

    result = await gateway.generate_story(make_request())

    assert result["intent_summary"] == "A valid response"
    assert captured["authorization"] == "Bearer test-token"
    assert captured["payload"]["target_context"]["npc_id"] == "vidalia"
    assert captured["payload"]["generation_budget"] == {
        "max_model_calls": 2,
        "max_event_proposals": 1,
        "max_active_goals": 2,
        "max_active_commitments": 3,
        "max_active_quests": 2,
    }
    assert "truth_level" not in captured["payload"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [408, 429, 500, 503])
async def test_retryable_http_status_is_transient(status_code: int) -> None:
    gateway = HttpModelGateway(
        "https://model.example/generate",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status_code, json={"error": "temporary"})
        ),
    )

    with pytest.raises(ModelGatewayTransientError):
        await gateway.generate_story(make_request())


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [400, 401, 403, 404])
async def test_non_retryable_http_status_is_permanent(status_code: int) -> None:
    gateway = HttpModelGateway(
        "https://model.example/generate",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(status_code, json={"error": "request"})
        ),
    )

    with pytest.raises(ModelGatewayPermanentError):
        await gateway.generate_story(make_request())


def test_external_gateway_is_opt_in(monkeypatch) -> None:
    monkeypatch.delenv("MODEL_GATEWAY_URL", raising=False)

    assert build_story_planner_from_env(object()) is None
