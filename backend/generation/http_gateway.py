"""HTTP transport for the provider-neutral ModelGateway contract."""

from collections.abc import Mapping
from typing import Any

import httpx

from backend.generation.gateway import (
    ModelGatewayPermanentError,
    ModelGatewayTransientError,
    ModelTurnRequest,
)


class HttpModelGateway:
    """POST ModelTurnRequest JSON and return one ModelStoryOutput-shaped object."""

    def __init__(
        self,
        endpoint: str,
        *,
        api_key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not endpoint.strip():
            raise ValueError("Model gateway endpoint cannot be empty")
        self._endpoint = endpoint
        self._api_key = api_key
        self._transport = transport

    async def generate_story(self, request: ModelTurnRequest) -> Mapping[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(transport=self._transport, timeout=None) as client:
                response = await client.post(
                    self._endpoint,
                    headers=headers,
                    json=request.model_dump(mode="json"),
                )
        except httpx.HTTPError as exc:
            raise ModelGatewayTransientError("Model gateway network failure") from exc

        if response.status_code in {408, 429} or response.status_code >= 500:
            raise ModelGatewayTransientError(
                f"Model gateway returned retryable HTTP {response.status_code}"
            )
        if response.status_code >= 400:
            raise ModelGatewayPermanentError(
                f"Model gateway rejected the request with HTTP {response.status_code}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise ModelGatewayTransientError("Model gateway returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise ModelGatewayTransientError("Model gateway response must be a JSON object")
        return payload
