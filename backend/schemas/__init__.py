"""Shared Pydantic contracts used by the backend modules and API layer."""

from .api_response import ApiError, GameTurnResponse
from .game_state import GameState, InventoryItem, NPCState, PlayerState, SceneState
from .parsed_action import ActionType, ParsedAction
from .player_action import InputType, PlayerAction
from .story import DialogueLine, EventProposal, SpeakerType, StoryProposal

__all__ = [
    "ActionType",
    "ApiError",
    "DialogueLine",
    "EventProposal",
    "GameState",
    "GameTurnResponse",
    "InputType",
    "InventoryItem",
    "NPCState",
    "ParsedAction",
    "PlayerAction",
    "PlayerState",
    "SceneState",
    "SpeakerType",
    "StoryProposal",
]
