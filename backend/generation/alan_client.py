"""Call the GPU's dedicated plain-dialogue Alan adapter."""

import os

import httpx

from backend.schemas.alan_chat import AlanModelRequest, AlanModelResponse


class AlanGatewayUnavailable(RuntimeError):
    pass


class AlanGatewayClient:
    def __init__(self, endpoint: str, api_key: str | None = None) -> None:
        self.endpoint = endpoint
        self.api_key = api_key

    async def generate(self, request: AlanModelRequest) -> AlanModelResponse:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            async with httpx.AsyncClient(timeout=65) as client:
                response = await client.post(
                    self.endpoint, json=request.model_dump(mode="json"), headers=headers
                )
            response.raise_for_status()
            return AlanModelResponse.model_validate(response.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise AlanGatewayUnavailable("艾倫通訊暫時無法接通，請稍後重試。") from exc


def build_alan_client_from_env() -> AlanGatewayClient | None:
    endpoint = os.getenv("ALAN_GATEWAY_URL", "").strip()
    if not endpoint and os.getenv("MODEL_GATEWAY_PROVIDER", "contract_http") == "contract_http":
        story_endpoint = os.getenv("MODEL_GATEWAY_URL", "").strip()
        if story_endpoint.endswith("/generate"):
            endpoint = story_endpoint[:-len("/generate")] + "/alan/generate"
    return AlanGatewayClient(endpoint, os.getenv("MODEL_GATEWAY_API_KEY") or None) if endpoint else None
