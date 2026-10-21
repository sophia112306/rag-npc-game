"""Health check endpoint for the backend service."""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field


router = APIRouter(tags=["health"])
SERVICE_NAME = "rag-npc-game"
APP_VERSION = "0.1.0"


class HealthResponse(BaseModel):
    """Response returned when the API process is alive."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    service: str = SERVICE_NAME
    version: str = APP_VERSION
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check backend health",
)
def health_check() -> HealthResponse:
    """Return a liveness response without checking database or AI services."""

    return HealthResponse()
