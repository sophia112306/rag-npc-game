"""Environment-driven assembly for the optional external model gateway."""

import os

from backend.generation.http_gateway import HttpModelGateway
from backend.generation.planner import GatewayStoryPlanner, NPCContextProvider


def build_story_planner_from_env(
    context_provider: NPCContextProvider,
) -> GatewayStoryPlanner | None:
    """Return no external planner unless MODEL_GATEWAY_URL is explicitly set."""

    endpoint = os.getenv("MODEL_GATEWAY_URL", "").strip()
    if not endpoint:
        return None

    try:
        timeout_seconds = float(os.getenv("MODEL_GATEWAY_TIMEOUT_SECONDS", "15"))
        max_attempts = int(os.getenv("MODEL_GATEWAY_MAX_ATTEMPTS", "2"))
    except ValueError as exc:
        raise ValueError("Invalid MODEL_GATEWAY timeout or attempt configuration") from exc

    gateway = HttpModelGateway(
        endpoint,
        api_key=os.getenv("MODEL_GATEWAY_API_KEY") or None,
    )
    return GatewayStoryPlanner(
        gateway,
        context_provider,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
    )
