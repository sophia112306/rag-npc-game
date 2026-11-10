"""Authorized context assembly, timeout, retry, and structured-output validation."""

import asyncio
from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import ValidationError

from backend.content.context_repository import CharacterDefinitionNotFoundError
from backend.generation.gateway import (
    ModelGateway,
    ModelGatewayPermanentError,
    ModelGatewayTransientError,
    ModelStoryOutput,
    ModelTurnRequest,
)
from backend.schemas.content import NPCGenerationContext
from backend.schemas.game_state import GameState
from backend.schemas.parsed_action import ParsedAction
from backend.schemas.player_action import PlayerAction
from backend.schemas.story import OperationType, StoryProposal


class NPCContextProvider(Protocol):
    async def get_generation_context(
        self,
        session_id: str,
        npc_id: str,
        current_turn: int,
    ) -> NPCGenerationContext: ...


class StoryGenerationUnavailableError(RuntimeError):
    """Safe public failure raised when no valid proposal can be obtained."""

    def __init__(self, code: str, attempts: int) -> None:
        self.code = code
        self.attempts = attempts
        super().__init__("Story generation is temporarily unavailable")


class GatewayStoryPlanner:
    """Turn authorized NPC context into a validated untrusted StoryProposal."""

    def __init__(
        self,
        gateway: ModelGateway,
        context_provider: NPCContextProvider,
        *,
        timeout_seconds: float = 15.0,
        max_attempts: int = 2,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be between one and three")
        self._gateway = gateway
        self._context_provider = context_provider
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts

    async def propose(
        self,
        action: PlayerAction,
        parsed_action: ParsedAction,
        state: GameState,
    ) -> StoryProposal:
        npc_id = action.target_npc_id or "vidalia"
        try:
            target_context = await self._context_provider.get_generation_context(
                action.session_id,
                npc_id,
                state.turn_count,
            )
        except CharacterDefinitionNotFoundError as exc:
            raise StoryGenerationUnavailableError("character_context_missing", 0) from exc

        request = ModelTurnRequest(
            session_id=action.session_id,
            turn_number=state.turn_count + 1,
            state_version=state.state_version,
            current_scene_id=state.current_scene_id,
            player_id=state.player.player_id,
            player_inventory=list(state.player.inventory),
            action_message=action.message,
            action_mode=action.action_mode,
            parsed_action=parsed_action,
            target_context=target_context,
            allowed_operations=[OperationType.TRANSFER_ITEM],
        )
        output = await self._generate_valid_output(request)
        return StoryProposal(
            session_id=action.session_id,
            turn_number=state.turn_count + 1,
            intent_summary=output.intent_summary,
            event_proposals=output.event_proposals,
        )

    async def _generate_valid_output(self, request: ModelTurnRequest) -> ModelStoryOutput:
        failure_code = "model_unavailable"
        attempts = 0
        for attempts in range(1, self._max_attempts + 1):
            try:
                raw_output = await asyncio.wait_for(
                    self._gateway.generate_story(request),
                    timeout=self._timeout_seconds,
                )
                return self._validate_output(raw_output)
            except TimeoutError:
                failure_code = "model_timeout"
            except ModelGatewayTransientError:
                failure_code = "model_unavailable"
            except ModelGatewayPermanentError as exc:
                raise StoryGenerationUnavailableError("model_configuration_error", attempts) from exc
            except ValidationError:
                failure_code = "invalid_model_output"
            except Exception:
                failure_code = "model_unavailable"

        raise StoryGenerationUnavailableError(failure_code, attempts)

    @staticmethod
    def _validate_output(raw_output: Mapping[str, Any]) -> ModelStoryOutput:
        return ModelStoryOutput.model_validate(raw_output)
