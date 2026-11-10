"""Environment-driven assembly for the optional external model gateway."""

import os

from backend.generation.http_gateway import HttpModelGateway
from backend.generation.openai_compatible_gateway import OpenAICompatibleChatGateway
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

    provider = os.getenv("MODEL_GATEWAY_PROVIDER", "contract_http").strip().lower()
    api_key = os.getenv("MODEL_GATEWAY_API_KEY") or None
    if provider == "contract_http":
        gateway = HttpModelGateway(endpoint, api_key=api_key)
    elif provider == "openai_compatible":
        model = os.getenv("MODEL_GATEWAY_MODEL", "").strip()
        if not model:
            raise ValueError(
                "MODEL_GATEWAY_MODEL is required for the openai_compatible provider"
            )
        response_format = os.getenv(
            "MODEL_GATEWAY_RESPONSE_FORMAT", "json_schema"
        ).strip()
        if response_format not in {"json_schema", "json_object"}:
            raise ValueError(
                "MODEL_GATEWAY_RESPONSE_FORMAT must be json_schema or json_object"
            )
        gateway = OpenAICompatibleChatGateway(
            endpoint,
            model,
            api_key=api_key,
            response_format=response_format,
        )
    else:
        raise ValueError(
            "MODEL_GATEWAY_PROVIDER must be contract_http or openai_compatible"
        )
    return GatewayStoryPlanner(
        gateway,
        context_provider,
        timeout_seconds=timeout_seconds,
        max_attempts=max_attempts,
    )
