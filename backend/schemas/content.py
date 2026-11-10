"""Contracts for immutable canon, character definitions, knowledge, and memory."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .character import CharacterProfile


class SettingCertainty(str, Enum):
    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"
    UNCONFIRMED = "unconfirmed"


class DisclosureScope(str, Enum):
    AUTHOR_ONLY = "author_only"
    CONDITIONAL = "conditional"
    PUBLIC = "public"


class SourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: str = Field(..., min_length=1, max_length=50)
    source_id: str = Field(..., min_length=1, max_length=200)
    locator: str | None = Field(default=None, max_length=500)


class WorldCanonEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    canon_id: str = Field(..., min_length=1, max_length=100)
    statement: str = Field(..., min_length=1)
    source: SourceReference
    certainty: SettingCertainty
    disclosure_scope: DisclosureScope
    status: str = Field(default="active", min_length=1, max_length=30)
    setting_version: int = Field(default=1, ge=1)


class CharacterDefinition(BaseModel):
    """Author-maintained character definition; private fields never go to player APIs."""

    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(..., min_length=1, max_length=100)
    public_profile: CharacterProfile
    private_profile: dict[str, Any] = Field(default_factory=dict)
    sources: list[SourceReference] = Field(default_factory=list)
    setting_version: int = Field(default=1, ge=1)
    completeness_status: str = Field(default="incomplete", min_length=1, max_length=30)


class KnowledgeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    knowledge_id: str
    subject_key: str
    content: str
    epistemic_status: str
    source_kind: str
    source_id: str | None = None
    acquired_turn: int
    provenance: dict[str, Any]


class MemoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    content: str
    memory_type: str
    source_event_id: str | None = None
    source_action_id: str | None = None
    occurred_turn: int
    importance: int
    provenance: dict[str, Any]


class NPCGenerationContext(BaseModel):
    """Private backend-only context prepared for a future ModelGateway call."""

    model_config = ConfigDict(extra="forbid")

    npc_id: str
    setting_version: int
    public_profile: dict[str, Any]
    private_profile: dict[str, Any]
    knowledge: list[KnowledgeItem]
    memories: list[MemoryItem]
    missing_data: list[str]
