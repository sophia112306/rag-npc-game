"""Sourced NPC goals and commitments used by the turn clock."""

from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProgressionSourceKind(str, Enum):
    AUTHOR = "author"
    ESTABLISHED_EVENT = "established_event"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CommitmentStatus(str, Enum):
    ACTIVE = "active"
    FULFILLED = "fulfilled"
    BROKEN = "broken"
    CANCELLED = "cancelled"


class NPCGoalRecordInput(BaseModel):
    """Validated write contract; goals need an author or established-event source."""

    model_config = ConfigDict(extra="forbid")

    goal_id: UUID = Field(default_factory=uuid4)
    session_id: str = Field(..., min_length=1, max_length=100)
    npc_id: str = Field(..., min_length=1, max_length=100)
    summary: str = Field(..., min_length=1, max_length=1_000)
    priority: int = Field(default=50, ge=0, le=100)
    status: GoalStatus = GoalStatus.ACTIVE
    created_turn: int = Field(..., ge=0)
    next_review_turn: int = Field(..., ge=0)
    source_kind: ProgressionSourceKind
    source_id: str = Field(..., min_length=1, max_length=100)
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def review_cannot_predate_creation(self):
        if self.next_review_turn < self.created_turn:
            raise ValueError("next_review_turn cannot predate created_turn")
        return self


class NPCGoalItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal_id: str
    npc_id: str
    summary: str
    priority: int
    created_turn: int
    next_review_turn: int
    source_kind: ProgressionSourceKind
    source_id: str
    provenance: dict[str, Any]


class CommitmentRecordInput(BaseModel):
    """Validated promise or obligation with explicit participants and source."""

    model_config = ConfigDict(extra="forbid")

    commitment_id: UUID = Field(default_factory=uuid4)
    session_id: str = Field(..., min_length=1, max_length=100)
    summary: str = Field(..., min_length=1, max_length=1_000)
    promisor_id: str = Field(..., min_length=1, max_length=100)
    promisee_id: str = Field(..., min_length=1, max_length=100)
    status: CommitmentStatus = CommitmentStatus.ACTIVE
    created_turn: int = Field(..., ge=0)
    due_turn: int | None = Field(default=None, ge=0)
    source_kind: ProgressionSourceKind
    source_id: str = Field(..., min_length=1, max_length=100)
    visibility: str = Field(default="player", pattern="^(player|backend)$")
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_participants_and_due_turn(self):
        if self.promisor_id == self.promisee_id:
            raise ValueError("A commitment requires two different participants")
        if self.due_turn is not None and self.due_turn < self.created_turn:
            raise ValueError("due_turn cannot predate created_turn")
        return self


class CommitmentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    commitment_id: str
    summary: str
    promisor_id: str
    promisee_id: str
    created_turn: int
    due_turn: int | None
    source_kind: ProgressionSourceKind
    source_id: str
    visibility: str
    provenance: dict[str, Any]
