"""Public runtime capabilities used to label optional integrations honestly."""

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict

from backend.schemas.story import OperationType


class CapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    generation_mode: Literal["rule_based", "external_model"]
    dynamic_dialogue: bool
    rag_integration: Literal["pending"] = "pending"
    voice_integration: Literal["pending"] = "pending"
    allowed_operations: list[OperationType]


router = APIRouter(prefix="/api", tags=["meta"])


@router.get(
    "/capabilities",
    response_model=CapabilitiesResponse,
    summary="Show optional integration status",
)
def get_capabilities(request: Request) -> CapabilitiesResponse:
    generation_mode = request.app.state.generation_mode
    return CapabilitiesResponse(
        generation_mode=generation_mode,
        dynamic_dialogue=True,
        allowed_operations=[
            OperationType.TRANSFER_ITEM,
            OperationType.ESTABLISH_COMMITMENT,
            OperationType.OFFER_QUEST,
            OperationType.CHANGE_SCENE,
        ],
    )
