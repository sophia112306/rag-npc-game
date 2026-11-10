"""Provider-neutral request, response, and error contracts for story generation."""

from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.content import NPCGenerationContext
from backend.schemas.parsed_action import ParsedAction
from backend.schemas.player_action import ActionMode
from backend.schemas.story import EventProposal, OperationType


class ModelTurnRequest(BaseModel):
    """Minimal authorized context sent to a model adapter for one turn."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=100)
    turn_number: int = Field(..., ge=1)
    state_version: int = Field(..., ge=1)
    current_scene_id: str = Field(..., min_length=1, max_length=100)
    player_id: str = Field(..., min_length=1, max_length=100)
    player_inventory: list[str] = Field(default_factory=list)
    action_message: str = Field(..., min_length=1, max_length=2_000)
    action_mode: ActionMode
    parsed_action: ParsedAction
    target_context: NPCGenerationContext
    allowed_operations: list[OperationType]


class ModelStoryOutput(BaseModel):
    """Structured model output before trusted session metadata is attached."""

    model_config = ConfigDict(extra="forbid")

    intent_summary: str = Field(default="", max_length=1_000)
    event_proposals: list[EventProposal] = Field(default_factory=list, max_length=3)


class ModelGatewayTransientError(RuntimeError):
    """A model-service failure that may succeed on a bounded retry."""


class ModelGatewayPermanentError(RuntimeError):
    """A configuration or request failure that should not be retried."""


class ModelGateway(Protocol):
    """Interface B's external model adapter must implement."""

    async def generate_story(self, request: ModelTurnRequest) -> Mapping[str, Any]: ...
