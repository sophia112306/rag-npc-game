"""Provider-neutral request, response, and error contracts for story generation."""

from collections.abc import Mapping
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.content import NPCGenerationContext
from backend.schemas.parsed_action import ParsedAction
from backend.schemas.player_action import ActionMode
from backend.schemas.story import EventProposal, OperationType


class GenerationBudget(BaseModel):
    """Hard first-version limits for one player-triggered world tick."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_model_calls: int = Field(default=2, ge=1, le=3)
    max_event_proposals: int = Field(default=1, ge=0, le=1)
    max_active_goals: int = Field(default=2, ge=0, le=2)
    max_active_commitments: int = Field(default=3, ge=0, le=3)
    max_active_quests: int = Field(default=2, ge=0, le=2)


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
    generation_budget: GenerationBudget = Field(default_factory=GenerationBudget)


class ModelNPCDialogue(BaseModel):
    """Subjective speech; backend assigns the authorized NPC identity."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=4_000)
    emotion: str | None = Field(default=None, max_length=50)


class ModelStoryOutput(BaseModel):
    """Structured model output before trusted session metadata is attached."""

    model_config = ConfigDict(extra="forbid")

    intent_summary: str = Field(default="", max_length=1_000)
    npc_dialogue: list[ModelNPCDialogue] = Field(..., min_length=1, max_length=3)
    event_proposals: list[EventProposal] = Field(default_factory=list, max_length=1)


class ModelGatewayTransientError(RuntimeError):
    """A model-service failure that may succeed on a bounded retry."""


class ModelGatewayPermanentError(RuntimeError):
    """A configuration or request failure that should not be retried."""


class ModelGateway(Protocol):
    """Interface B's external model adapter must implement."""

    async def generate_story(self, request: ModelTurnRequest) -> Mapping[str, Any]: ...
