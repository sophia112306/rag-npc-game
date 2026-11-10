from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class InputType(str, Enum):
    TEXT = "text"
    SPEECH_TRANSCRIPT = "speech_transcript"

class ActionMode(str, Enum):
    DIALOGUE = "dialogue"
    INTERACTION = "interaction"
    MOVEMENT = "movement"

class PlayerAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=100)
    action_id: UUID
    input_type: InputType = InputType.TEXT
    message: str = Field(..., min_length=1, max_length=2_000)
    target_npc_id: Optional[str] = Field(default=None, max_length=100)
    action_mode: ActionMode = ActionMode.DIALOGUE
    expected_state_version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
