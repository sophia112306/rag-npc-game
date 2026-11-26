"""Player-only retinal HUD contract for Alan's communication channel."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AlanTone = Literal["calm", "urgent", "interference", "override", "silent"]


class AlanHud(BaseModel):
    """Information visible only to the protagonist through the retinal HUD.

    This is deliberately not a dialogue line or NPC state. It is a compact,
    player-view signal that can be rendered without making Alan appear in the
    world or requiring a trained character model. Internal progression values
    such as ``usurp`` stay on the server and are not part of this contract.
    """

    model_config = ConfigDict(extra="forbid")

    visible: bool = True
    label: str = Field(default="視網膜連線", min_length=1, max_length=40)
    display_value: int = Field(default=0, ge=0, le=100)
    tone: AlanTone = "calm"
    message: str = Field(..., min_length=1, max_length=300)
    persistent: bool = False
    countdown_turns: int | None = Field(default=None, ge=0, le=3)
    event_key: str | None = Field(default=None, max_length=100)
