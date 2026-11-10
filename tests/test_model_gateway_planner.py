"""Provider-neutral model planner timeout, retry, and context-boundary tests."""

import asyncio
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest

from backend.content.characters import CHARACTER_PROFILES
from backend.generation.gateway import ModelGatewayPermanentError, ModelTurnRequest
from backend.generation.planner import GatewayStoryPlanner, StoryGenerationUnavailableError
from backend.schemas.content import NPCGenerationContext
from backend.schemas.game_state import GameState, PlayerState
from backend.schemas.parsed_action import ParsedAction
from backend.schemas.player_action import PlayerAction


class FixedContextProvider:
    async def get_generation_context(self, session_id, npc_id, current_turn):
        return NPCGenerationContext(
            npc_id=npc_id,
            setting_version=1,
            public_profile=CHARACTER_PROFILES["vidalia"].model_dump(mode="json"),
            private_profile={"core_constraint": "Do not invent missing canon."},
            knowledge=[],
            memories=[],
            missing_data=["character_definition_incomplete"],
        )


class SequenceGateway:
    def __init__(self, *results: object) -> None:
        self.results = list(results)
        self.requests: list[ModelTurnRequest] = []

    async def generate_story(self, request: ModelTurnRequest) -> Mapping[str, Any]:
        self.requests.append(request)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def make_inputs() -> tuple[PlayerAction, ParsedAction, GameState]:
    action = PlayerAction(
        session_id="model-session",
        action_id=uuid4(),
        message="你願意交換線索嗎？",
        target_npc_id="vidalia",
        expected_state_version=1,
    )
    parsed = ParsedAction(intent="dialogue", target_ids=["vidalia"])
    state = GameState(
        session_id=action.session_id,
        current_scene_id="minglin",
        player=PlayerState(player_id="player", inventory=["map_fragment"]),
        axis=50,
        truth_level=2,
        flags={"private_secret": True},
    )
    return action, parsed, state


@pytest.mark.asyncio
async def test_planner_sends_only_explicit_authorized_context() -> None:
    gateway = SequenceGateway({"intent_summary": "Respond cautiously.", "event_proposals": []})
    planner = GatewayStoryPlanner(gateway, FixedContextProvider())
    action, parsed, state = make_inputs()

    proposal = await planner.propose(action, parsed, state)

    assert proposal.session_id == action.session_id
    assert proposal.turn_number == 1
    assert proposal.intent_summary == "Respond cautiously."
    request_json = gateway.requests[0].model_dump_json()
    assert "private_secret" not in request_json
    assert "truth_level" not in request_json
    assert '"axis"' not in request_json
    assert "character_definition_incomplete" in request_json
    assert "map_fragment" in request_json


@pytest.mark.asyncio
async def test_invalid_output_is_retried_once_then_accepted() -> None:
    gateway = SequenceGateway(
        {"unexpected": "shape"},
        {"intent_summary": "Valid second response.", "event_proposals": []},
    )
    planner = GatewayStoryPlanner(gateway, FixedContextProvider(), max_attempts=2)
    action, parsed, state = make_inputs()

    proposal = await planner.propose(action, parsed, state)

    assert proposal.intent_summary == "Valid second response."
    assert len(gateway.requests) == 2


@pytest.mark.asyncio
async def test_timeout_stops_after_configured_attempts() -> None:
    class NeverReturnsGateway:
        def __init__(self) -> None:
            self.calls = 0

        async def generate_story(self, request):
            self.calls += 1
            await asyncio.Event().wait()

    gateway = NeverReturnsGateway()
    planner = GatewayStoryPlanner(
        gateway,
        FixedContextProvider(),
        timeout_seconds=0.001,
        max_attempts=2,
    )
    action, parsed, state = make_inputs()

    with pytest.raises(StoryGenerationUnavailableError) as error:
        await planner.propose(action, parsed, state)

    assert error.value.code == "model_timeout"
    assert error.value.attempts == 2
    assert gateway.calls == 2


@pytest.mark.asyncio
async def test_permanent_gateway_error_is_not_retried() -> None:
    gateway = SequenceGateway(ModelGatewayPermanentError("bad credentials"))
    planner = GatewayStoryPlanner(gateway, FixedContextProvider(), max_attempts=3)
    action, parsed, state = make_inputs()

    with pytest.raises(StoryGenerationUnavailableError) as error:
        await planner.propose(action, parsed, state)

    assert error.value.code == "model_configuration_error"
    assert error.value.attempts == 1
    assert len(gateway.requests) == 1
