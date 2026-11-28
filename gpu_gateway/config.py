"""Environment configuration for the GPU-side NPC adapter gateway."""

from dataclasses import dataclass, field
import json
import os
from typing import Literal


DEFAULT_NPC_MODEL_MAP = {
    "alan": "alan-lora",
    "andre": "andre-lora",
    "dasso": "dasso-lora",
    "menmesvento": "menmesvento-lora",
    "seth": "seth-lora",
    "syra": "syra-lora",
    "vidalia": "vidalia-lora",
    "veta": "veta-lora",
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
    # Narrator events need a judgement and an independent review even when
    # NPC generation is limited to one upstream attempt.
    narrator_upstream_max_attempts: int | None = None
    # 敘事 AI（/narrate）用基礎模型，不掛 NPC LoRA
    narrator_model: str | None = DEFAULT_BASE_MODEL
    # Production enables a base-model semantic review after each NPC draft.
    # Directly constructed test settings remain opt-in for focused unit tests.
    semantic_review_enabled: bool = False
    # Raw dialogue may contain personal data.  Auditing is therefore disabled
    # unless both an absolute destination and an HMAC key are configured.
    review_audit_path: str | None = None
    review_audit_hmac_key: str | None = None

    def __post_init__(self) -> None:
        if self.narrator_upstream_max_attempts is not None and not 1 <= self.narrator_upstream_max_attempts <= 3:
            raise ValueError("narrator_upstream_max_attempts must be between 1 and 3")
        if bool(self.review_audit_path) != bool(self.review_audit_hmac_key):
            raise ValueError(
                "review_audit_path and review_audit_hmac_key "
                "must be configured together"
            )
        if self.review_audit_path and not os.path.isabs(self.review_audit_path):
            raise ValueError("review_audit_path must be absolute")
        if self.review_audit_hmac_key and len(self.review_audit_hmac_key) < 16:
            raise ValueError(
                "review_audit_hmac_key must contain at least 16 characters"
            )

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
        raw_narrator_attempts = os.getenv("NARRATOR_UPSTREAM_MAX_ATTEMPTS", "").strip()
        try:
            narrator_attempts = int(raw_narrator_attempts) if raw_narrator_attempts else None
        except ValueError as exc:
            raise ValueError("NARRATOR_UPSTREAM_MAX_ATTEMPTS must be an integer") from exc

        fallback = os.getenv("NPC_FALLBACK_MODEL", DEFAULT_BASE_MODEL).strip()
        narrator = os.getenv("NARRATOR_MODEL", DEFAULT_BASE_MODEL).strip()
        semantic_review_text = os.getenv(
            "NPC_SEMANTIC_REVIEW_ENABLED", "true"
        ).strip().casefold()
        if semantic_review_text not in {"1", "0", "true", "false", "yes", "no"}:
            raise ValueError(
                "NPC_SEMANTIC_REVIEW_ENABLED must be true or false"
            )
        semantic_review_enabled = semantic_review_text in {"1", "true", "yes"}
        review_audit_path = os.getenv("NPC_REVIEW_AUDIT_PATH", "").strip()
        review_audit_hmac_key = os.getenv(
            "NPC_REVIEW_AUDIT_HMAC_KEY", ""
        ).strip()
        if bool(review_audit_path) != bool(review_audit_hmac_key):
            raise ValueError(
                "NPC_REVIEW_AUDIT_PATH and NPC_REVIEW_AUDIT_HMAC_KEY "
                "must be configured together"
            )
        if review_audit_path and not os.path.isabs(review_audit_path):
            raise ValueError("NPC_REVIEW_AUDIT_PATH must be absolute")
        if review_audit_hmac_key and len(review_audit_hmac_key) < 16:
            raise ValueError(
                "NPC_REVIEW_AUDIT_HMAC_KEY must contain at least 16 characters"
            )
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
            narrator_upstream_max_attempts=narrator_attempts,
            narrator_model=narrator or None,
            semantic_review_enabled=semantic_review_enabled,
            review_audit_path=review_audit_path or None,
            review_audit_hmac_key=review_audit_hmac_key or None,
        )
