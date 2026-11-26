"""Replaceable model-generation boundaries."""

from .gateway import (
    GenerationBudget,
    ModelGateway,
    ModelGatewayPermanentError,
    ModelGatewayResponseRejectedError,
    ModelGatewayTransientError,
    ModelNPCDialogue,
    ModelStoryOutput,
    ModelTurnRequest,
    TurnGuidance,
    TurnGuidanceAction,
)
from .http_gateway import HttpModelGateway
from .openai_compatible_gateway import OpenAICompatibleChatGateway
from .planner import GatewayStoryPlanner, StoryGenerationUnavailableError
from .rule_based_planner import RuleBasedStoryPlanner

__all__ = [
    "GatewayStoryPlanner",
    "GenerationBudget",
    "HttpModelGateway",
    "ModelGateway",
    "ModelGatewayPermanentError",
    "ModelGatewayResponseRejectedError",
    "ModelGatewayTransientError",
    "ModelNPCDialogue",
    "ModelStoryOutput",
    "ModelTurnRequest",
    "TurnGuidance",
    "TurnGuidanceAction",
    "OpenAICompatibleChatGateway",
    "RuleBasedStoryPlanner",
    "StoryGenerationUnavailableError",
]
