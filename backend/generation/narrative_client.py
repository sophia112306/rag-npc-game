"""Call the GPU gateway's narrative-AI endpoint (``/narrate``).

規格 v3：每回合先由敘事 AI 判讀玩家發言、提出數值變化，再由 NPC 模型說話。
敘事 AI 只提出數字；上限、封頂與防刷分由 StateRules 執行。
"""

import os

import httpx

from backend.schemas.api_response import NarrativeAIResponse
from backend.schemas.narrative_ai import NarrativeAIRequest


class NarrativeAIUnavailable(RuntimeError):
    """The narrative AI could not produce a usable judgement this turn."""


class NarrativeGatewayClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str | None = None,
        timeout_seconds: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def judge(self, request: NarrativeAIRequest) -> NarrativeAIResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(
                transport=self.transport, timeout=self.timeout_seconds
            ) as client:
                response = await client.post(
                    self.endpoint, json=request.model_dump(mode="json"), headers=headers
                )
            response.raise_for_status()
            return NarrativeAIResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise NarrativeAIUnavailable("Narrative AI judgement failed") from exc


def build_narrative_client_from_env() -> NarrativeGatewayClient | None:
    """Opt-in: only enabled when NARRATIVE_GATEWAY_URL is set explicitly."""

    endpoint = os.getenv("NARRATIVE_GATEWAY_URL", "").strip()
    if not endpoint:
        return None
    try:
        timeout_seconds = float(os.getenv("NARRATIVE_GATEWAY_TIMEOUT_SECONDS", "20"))
    except ValueError as exc:
        raise ValueError("NARRATIVE_GATEWAY_TIMEOUT_SECONDS must be numeric") from exc
    if timeout_seconds <= 0:
        raise ValueError("NARRATIVE_GATEWAY_TIMEOUT_SECONDS must be greater than zero")
    api_key = os.getenv("NARRATIVE_GATEWAY_API_KEY") or os.getenv("MODEL_GATEWAY_API_KEY") or None
    return NarrativeGatewayClient(endpoint, api_key, timeout_seconds)
