"""Schemas for generated dialogue, proposed operations, and rule decisions."""

from enum import Enum
from typing import Annotated, Literal
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


class OperationType(str, Enum):
    """State-changing commands currently supported by the rule boundary."""

    TRANSFER_ITEM = "transfer_item"
    ESTABLISH_COMMITMENT = "establish_commitment"
    OFFER_QUEST = "offer_quest"


class TransferItemOperation(BaseModel):
    """Request an ownership transfer without creating an item."""

    model_config = ConfigDict(extra="forbid")

    operation_type: Literal[OperationType.TRANSFER_ITEM] = OperationType.TRANSFER_ITEM
    item_id: str = Field(..., min_length=1, max_length=100)
    from_entity_id: str = Field(..., min_length=1, max_length=100)
    to_entity_id: str = Field(..., min_length=1, max_length=100)


class EstablishCommitmentOperation(BaseModel):
    """Propose a sourced obligation between two registered entities."""

    model_config = ConfigDict(extra="forbid")

    operation_type: Literal[OperationType.ESTABLISH_COMMITMENT] = (
        OperationType.ESTABLISH_COMMITMENT
    )
    summary: str = Field(..., min_length=1, max_length=1_000)
    promisor_id: str = Field(..., min_length=1, max_length=100)
    promisee_id: str = Field(..., min_length=1, max_length=100)
    due_in_turns: int | None = Field(default=None, ge=1, le=20)


class OfferQuestOperation(BaseModel):
    """Offer, but do not auto-accept or complete, a dynamic quest."""

    model_config = ConfigDict(extra="forbid")

    operation_type: Literal[OperationType.OFFER_QUEST] = OperationType.OFFER_QUEST
    title: str = Field(..., min_length=1, max_length=200)
    summary: str = Field(..., min_length=1, max_length=1_000)
    giver_id: str = Field(..., min_length=1, max_length=100)
    recipient_id: str = Field(..., min_length=1, max_length=100)
    due_in_turns: int | None = Field(default=None, ge=1, le=30)


ProposedOperation = Annotated[
    TransferItemOperation | EstablishCommitmentOperation | OfferQuestOperation,
    Field(discriminator="operation_type"),
]


class EventProposal(BaseModel):
    """A structured event suggestion for C's validator and state manager."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=1_000)
    actor_id: str = Field(..., min_length=1, max_length=100)
    target_id: str | None = Field(default=None, max_length=100)
    cause_event_id: UUID | None = None
    operations: list[ProposedOperation] = Field(..., min_length=1, max_length=5)
    witness_ids: list[str] = Field(default_factory=list, max_length=20)
    visible_to_player: bool = True


class ProposalStatus(str, Enum):
    """Whether a complete proposed event became a world fact."""

    APPROVED = "approved"
    REJECTED = "rejected"


class EstablishedEvent(BaseModel):
    """A backend-approved event safe to persist as an objective fact."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    event_type: str
    description: str
    actor_id: str
    target_id: str | None = None
    cause_event_id: UUID | None = None
    effect: dict[str, object]
    visibility: dict[str, object]


class ProposalDecision(BaseModel):
    """Traceable rule decision for one event proposal."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID
    status: ProposalStatus
    reason_code: str = Field(..., min_length=1, max_length=100)
    reason: str = Field(..., min_length=1, max_length=500)
    established_event: EstablishedEvent | None = None


class StoryProposal(BaseModel):
    """LLM output that is still a proposal until validated and applied."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: UUID = Field(default_factory=uuid4)
    session_id: str = Field(..., min_length=1, max_length=100)
    turn_number: int = Field(..., ge=0)
    intent_summary: str = Field(default="", max_length=1_000)
    proposed_dialogue: list[DialogueLine] = Field(default_factory=list, max_length=3)
    event_proposals: list[EventProposal] = Field(default_factory=list)
    next_scene_id: str | None = Field(default=None, max_length=100)


class ResolvedStory(BaseModel):
    """Player-visible narrative built only after proposal resolution."""

    model_config = ConfigDict(extra="forbid")

    dialogue: list[DialogueLine] = Field(default_factory=list)
    established_events: list[EstablishedEvent] = Field(default_factory=list)

