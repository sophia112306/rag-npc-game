"""Schema for the structured action produced from a PlayerAction."""

from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ActionType(str, Enum):
    """Supported high-level intentions understood by the game rules."""

    ASK = "ask"
    MOVE = "move"
    INTERACT = "interact"
    USE_ITEM = "use_item"
    TAKE_ITEM = "take_item"
    GIVE_ITEM = "give_item"
    ATTACK = "attack"
    REST = "rest"
    HELP = "help"
    UNKNOWN = "unknown"


class ParsedAction(BaseModel):
    """Machine-readable interpretation consumed by validation and state logic."""

    model_config = ConfigDict(extra="forbid")

    source_action_id: UUID = Field(..., description="The PlayerAction that was parsed")
    action_type: ActionType
    target: str | None = Field(default=None, max_length=200)
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)

