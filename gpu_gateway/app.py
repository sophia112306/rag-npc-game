"""FastAPI contract gateway in front of a multi-LoRA vLLM server."""

import asyncio
import hmac

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Response, status
from pydantic import ValidationError

from backend.generation.gateway import (
    ModelGatewayPermanentError,
    ModelGatewayResponseRejectedError,
    ModelGatewayTransientError,
    ModelStoryOutput,
    ModelTurnRequest,
)

from .config import GatewaySettings
from .router import (
    NPCAdapterRouter,
    UnsupportedNPCError,
    UpstreamHealthError,
    validation_error_detail,
)


def create_app(
    settings: GatewaySettings | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    resolved = settings or GatewaySettings.from_env()
    adapter_router = NPCAdapterRouter(resolved, transport=transport)
    application = FastAPI(
        title="RAG NPC Multi-LoRA Gateway",
        version="1.0.0",
        description=(
            "Routes the game's authorized ModelTurnRequest to one NPC LoRA "
            "and returns ModelStoryOutput."
        ),
    )

    def require_bearer(
        authorization: str | None = Header(default=None),
    ) -> None:
        expected_key = resolved.inbound_api_key
        if not expected_key:
            return
        expected = f"Bearer {expected_key}"
        if authorization is None or not hmac.compare_digest(
            authorization, expected
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"code": "INVALID_GATEWAY_TOKEN"},
            )

    @application.get("/health")
    async def health(_: None = Depends(require_bearer)) -> dict[str, object]:
        try:
            return await adapter_router.health()
        except UpstreamHealthError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "VLLM_NOT_READY", "message": str(exc)},
            ) from exc

    @application.get("/metrics")
    async def metrics(_: None = Depends(require_bearer)) -> dict[str, object]:
        return adapter_router.metrics()

    @application.post("/generate", response_model=ModelStoryOutput)
    async def generate(
        request: ModelTurnRequest,
        response: Response,
        _: None = Depends(require_bearer),
    ) -> ModelStoryOutput:
        try:
            result = await adapter_router.generate_with_trace(request)
            response.headers["X-NPC-Generation-Source"] = result.source
            response.headers["X-NPC-Model-ID"] = result.model_id
            response.headers["X-NPC-Route-Kind"] = result.route_kind
            response.headers["X-NPC-Upstream-Attempts"] = str(
                result.upstream_attempts
            )
            response.headers["Server-Timing"] = (
                f"npc-gateway;dur={result.latency_ms:.2f}"
            )
            return result.output
        except UnsupportedNPCError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={"code": "UNSUPPORTED_NPC", "message": str(exc)},
            ) from exc
        except asyncio.TimeoutError as exc:
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={"code": "VLLM_TIMEOUT"},
            ) from exc
        except ModelGatewayResponseRejectedError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"code": "MODEL_RESPONSE_REJECTED"},
            ) from exc
        except ModelGatewayPermanentError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"code": "VLLM_REQUEST_REJECTED", "message": str(exc)},
            ) from exc
        except ModelGatewayTransientError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"code": "VLLM_UNAVAILABLE", "message": str(exc)},
            ) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "INVALID_MODEL_OUTPUT",
                    "message": validation_error_detail(exc),
                },
            ) from exc

    application.state.adapter_router = adapter_router
    return application


app = create_app()
