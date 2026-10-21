"""Schemas for generated dialogue and proposed game events."""

from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class SpeakerType(str, Enum):
    """Role of a speaker in a generated story response."""

    NPC = "npc"
    NARRATOR = "narrator"


class DialogueLine(BaseModel):
    """One line of NPC dialogue or narration shown to the player."""

    model_config = ConfigDict(extra="forbid")

    speaker_type: SpeakerType
    speaker_id: str | None = Field(default=None, max_length=100)
    speaker_name: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=4_000)
    emotion: str | None = Field(default=None, max_length=50)


class EventProposal(BaseModel):
    """A structured event suggestion for C's validator and state manager."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=1_000)
    actor_id: str | None = Field(default=None, max_length=100)
    target_id: str | None = Field(default=None, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


class StoryProposal(BaseModel):
    """LLM output that is still a proposal until validated and applied."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID = Field(default_factory=uuid4)
    session_id: str = Field(..., min_length=1, max_length=100)
    turn_number: int = Field(..., ge=0)
    dialogue: list[DialogueLine] = Field(default_factory=list)
    event_proposals: list[EventProposal] = Field(default_factory=list)
    next_scene_id: str | None = Field(default=None, max_length=100)

