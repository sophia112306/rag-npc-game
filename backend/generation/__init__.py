"""Replaceable model-generation boundaries."""

from .gateway import (
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
    "HttpModelGateway",
    "ModelGateway",
    "ModelGatewayPermanentError",
    "ModelGatewayTransientError",
    "ModelNPCDialogue",
    "ModelStoryOutput",
    "ModelTurnRequest",
    "StoryGenerationUnavailableError",
]
