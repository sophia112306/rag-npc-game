"""Player-visible action choices generated from authoritative session state."""

from pydantic import BaseModel, ConfigDict, Field

from .player_action import ActionMode


class PlayerChoice(BaseModel):
    """One safe shortcut that submits an ordinary validated player action."""

    model_config = ConfigDict(extra="forbid")

    choice_id: str = Field(..., min_length=1, max_length=100)
    label: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=2_000)
    target_npc_id: str | None = Field(default=None, max_length=100)
    action_mode: ActionMode = ActionMode.DIALOGUE
    destination_scene_id: str | None = Field(default=None, max_length=100)
