"""Shared Pydantic contracts used by the backend modules and APIs."""

from .api_response import ApiError, DeltaPayload, GameTurnResponse, NarrativeAIResponse
from .character import CharacterProfile
from .game_state import GameState, InventoryItem, NPCState, PlayerState, SceneState, StoryPhase
from .parsed_action import ActionType, ParsedAction
from .player_action import ActionMode, InputType, PlayerAction
from .story import DialogueLine, EventProposal, SpeakerType, StoryProposal

__all__ = [
    "ActionType",
    "ActionMode",
    "ApiError",
    "CharacterProfile",
    "DeltaPayload",
    "DialogueLine",
    "EventProposal",
    "GameState",
    "GameTurnResponse",
    "InputType",
    "InventoryItem",
    "NarrativeAIResponse",
    "NPCState",
    "ParsedAction",
    "PlayerAction",
    "PlayerState",
    "SceneState",
    "SpeakerType",
    "StoryPhase",
    "StoryProposal",
]
