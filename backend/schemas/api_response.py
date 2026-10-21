"""Typed response contracts exposed by the FastAPI layer."""

from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .game_state import GameState
from .parsed_action import ParsedAction
from .story import StoryProposal


class ApiError(BaseModel):
    """Stable error shape for frontend handling and logging."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=500)
    details: dict[str, str] = Field(default_factory=dict)


class GameTurnResponse(BaseModel):
    """Response returned after one player action is processed."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID = Field(default_factory=uuid4)
    session_id: str = Field(..., min_length=1, max_length=100)
    turn_number: int = Field(..., ge=0)
    parsed_action: ParsedAction
    story: StoryProposal
    state: GameState

