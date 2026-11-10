"""Replaceable model-generation boundaries."""

from .gateway import (
    GenerationBudget,
    ModelGateway,
    ModelGatewayPermanentError,
    ModelGatewayTransientError,
    ModelNPCDialogue,
    ModelStoryOutput,
    ModelTurnRequest,
)
from .http_gateway import HttpModelGateway
from .planner import GatewayStoryPlanner, StoryGenerationUnavailableError

__all__ = [
    "GatewayStoryPlanner",
    "GenerationBudget",
    "HttpModelGateway",
    "ModelGateway",
    "ModelGatewayPermanentError",
    "ModelGatewayTransientError",
    "ModelNPCDialogue",
    "ModelStoryOutput",
    "ModelTurnRequest",
    "StoryGenerationUnavailableError",
]
