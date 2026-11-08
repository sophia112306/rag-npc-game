"""Shared Pydantic contracts used by the backend modules and APIs."""

from .api_response import ApiError, DeltaPayload, GameTurnResponse, NarrativeAIResponse
from .game_state import GameState, InventoryItem, NPCState, PlayerState, SceneState, StoryPhase
from .parsed_action import ActionType, ParsedAction
from .player_action import InputType, PlayerAction

__all__ = [
    "ActionType",
    "ApiError",
    "DeltaPayload",
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
    "StoryPhase",
]