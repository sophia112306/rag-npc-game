"""Shared Pydantic contracts used by the backend modules and APIs."""

from .api_response import ApiError, DeltaPayload, GameTurnResponse, NarrativeAIResponse
from .character import CharacterProfile
from .content import (
    CharacterDefinition,
    DisclosureScope,
    KnowledgeItem,
    KnowledgeRecordInput,
    MemoryItem,
    MemoryRecordInput,
    NPCGenerationContext,
    SettingCertainty,
    SourceReference,
    WorldCanonEntry,
)
from .game_state import GameState, InventoryItem, NPCState, PlayerState, SceneState, StoryPhase
from .parsed_action import ActionType, ParsedAction
from .player_action import ActionMode, InputType, PlayerAction
from .player_view import NPCPublicStateView, PlayerIdentityView, PlayerViewState
from .story import (
    DialogueLine,
    EstablishedEvent,
    EventProposal,
    OperationType,
    ProposalDecision,
    ProposalStatus,
    ResolvedStory,
    SpeakerType,
    StoryProposal,
    TransferItemOperation,
)

__all__ = [
    "ActionType",
    "ActionMode",
    "ApiError",
    "CharacterProfile",
    "CharacterDefinition",
    "DisclosureScope",
    "DeltaPayload",
    "DialogueLine",
    "EstablishedEvent",
    "EventProposal",
    "GameState",
    "GameTurnResponse",
    "InputType",
    "InventoryItem",
    "NarrativeAIResponse",
    "KnowledgeItem",
    "KnowledgeRecordInput",
    "MemoryItem",
    "MemoryRecordInput",
    "NPCGenerationContext",
    "NPCState",
    "NPCPublicStateView",
    "OperationType",
    "ParsedAction",
    "PlayerAction",
    "PlayerIdentityView",
    "PlayerState",
    "PlayerViewState",
    "ProposalDecision",
    "ProposalStatus",
    "ResolvedStory",
    "SceneState",
    "SpeakerType",
    "SettingCertainty",
    "SourceReference",
    "StoryPhase",
    "StoryProposal",
    "TransferItemOperation",
    "WorldCanonEntry",
]
