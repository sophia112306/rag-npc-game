from pydantic import BaseModel
from typing import Optional
from enum import Enum

class InputType(str, Enum):
    TEXT = "text"
    SPEECH_TRANSCRIPT = "speech_transcript"

class ActionMode(str, Enum):
    DIALOGUE = "dialogue"
    INTERACTION = "interaction"
    MOVEMENT = "movement"

class PlayerAction(BaseModel):
    session_id: str
    action_id: str
    input_type: InputType = InputType.TEXT
    message: str
    target_npc_id: Optional[str] = None
    action_mode: ActionMode = ActionMode.DIALOGUE
    expected_state_version: int = 1