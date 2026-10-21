"""Request schema for raw input submitted by a player."""

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class InputType(str, Enum):
    """The channel through which the player's input was collected."""

    TEXT = "text"
    VOICE = "voice"


class PlayerAction(BaseModel):
    """Raw player input sent to the game-turn endpoint."""

    model_config = ConfigDict(extra="forbid")

    action_id: UUID = Field(default_factory=uuid4, description="Unique ID for idempotency and tracing")
    session_id: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=2_000)
    input_type: InputType = InputType.TEXT
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

