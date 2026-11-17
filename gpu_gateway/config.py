"""Environment configuration for the GPU-side NPC adapter gateway."""

from dataclasses import dataclass, field
import json
import os
from typing import Literal


DEFAULT_NPC_MODEL_MAP = {
    "menmesvento": "menmesvento-lora",
    "vidalia": "vidalia-lora",
}
DEFAULT_BASE_MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"


@dataclass(frozen=True)
class GatewaySettings:
    """Settings shared by the lightweight router and its health endpoint."""

    upstream_base_url: str = "http://127.0.0.1:8001/v1"
    upstream_api_key: str | None = None
    inbound_api_key: str | None = None
    npc_model_map: dict[str, str] = field(
        default_factory=lambda: dict(DEFAULT_NPC_MODEL_MAP)
    )
    fallback_model: str | None = DEFAULT_BASE_MODEL
    response_format: Literal["json_schema", "json_object"] = "json_schema"
    upstream_timeout_seconds: float = 60.0
    upstream_max_attempts: int = 2

    @classmethod
    def from_env(cls) -> "GatewaySettings":
        raw_map = os.getenv("NPC_MODEL_MAP", "").strip()
        if raw_map:
            try:
                parsed_map = json.loads(raw_map)
            except json.JSONDecodeError as exc:
                raise ValueError("NPC_MODEL_MAP must be valid JSON") from exc
            if not isinstance(parsed_map, dict) or not all(
                isinstance(key, str)
                and key.strip()
                and isinstance(value, str)
                and value.strip()
                for key, value in parsed_map.items()
            ):
                raise ValueError("NPC_MODEL_MAP must map NPC IDs to model IDs")
            npc_model_map = {
                key.strip(): value.strip() for key, value in parsed_map.items()
            }
        else:
            npc_model_map = dict(DEFAULT_NPC_MODEL_MAP)

        response_format = os.getenv(
            "VLLM_RESPONSE_FORMAT", "json_schema"
        ).strip()
        if response_format not in {"json_schema", "json_object"}:
            raise ValueError(
                "VLLM_RESPONSE_FORMAT must be json_schema or json_object"
            )
        try:
            timeout_seconds = float(
                os.getenv("VLLM_UPSTREAM_TIMEOUT_SECONDS", "60")
            )
        except ValueError as exc:
            raise ValueError(
                "VLLM_UPSTREAM_TIMEOUT_SECONDS must be numeric"
            ) from exc
        if timeout_seconds <= 0:
            raise ValueError(
                "VLLM_UPSTREAM_TIMEOUT_SECONDS must be greater than zero"
            )
        try:
            max_attempts = int(os.getenv("VLLM_UPSTREAM_MAX_ATTEMPTS", "2"))
        except ValueError as exc:
            raise ValueError(
                "VLLM_UPSTREAM_MAX_ATTEMPTS must be an integer"
            ) from exc
        if not 1 <= max_attempts <= 3:
            raise ValueError(
                "VLLM_UPSTREAM_MAX_ATTEMPTS must be between 1 and 3"
            )

        fallback = os.getenv("NPC_FALLBACK_MODEL", DEFAULT_BASE_MODEL).strip()
        return cls(
            upstream_base_url=os.getenv(
                "VLLM_BASE_URL", "http://127.0.0.1:8001/v1"
            ).strip(),
            upstream_api_key=os.getenv("VLLM_API_KEY") or None,
            inbound_api_key=os.getenv("NPC_GATEWAY_API_KEY") or None,
            npc_model_map=npc_model_map,
            fallback_model=fallback or None,
            response_format=response_format,
            upstream_timeout_seconds=timeout_seconds,
            upstream_max_attempts=max_attempts,
        )
