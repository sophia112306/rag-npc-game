"""Game endpoints exposed to the frontend."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from backend.orchestration.game_orchestrator import (
    GameOrchestrator,
    SessionNotFoundError,
)
from backend.schemas.api_response import GameTurnResponse
from backend.schemas.game_state import GameState
from backend.schemas.player_action import PlayerAction


class StartGameRequest(BaseModel):
    """Request body used to create or resume a game session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=100)


router = APIRouter(prefix="/api/game", tags=["game"])
_orchestrator = GameOrchestrator()


def get_orchestrator() -> GameOrchestrator:
    """Return the shared in-memory orchestrator for this process."""

    return _orchestrator


@router.post(
    "/start",
    response_model=GameState,
    status_code=status.HTTP_201_CREATED,
    summary="Start a game session",
)
async def start_game(
    request: StartGameRequest,
    orchestrator: GameOrchestrator = Depends(get_orchestrator),
) -> GameState:
    """Create a new session or return the existing session state."""

    return await orchestrator.start_game(request.session_id)


@router.post(
    "/turn",
    response_model=GameTurnResponse,
    summary="Submit one player action",
)
async def submit_player_action(
    action: PlayerAction,
    orchestrator: GameOrchestrator = Depends(get_orchestrator),
) -> GameTurnResponse:
    """Process one action through the current orchestration skeleton."""

    try:
        return await orchestrator.process_turn(action)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": str(exc)},
        ) from exc


@router.get(
    "/{session_id}/state",
    response_model=GameState,
    summary="Get the current game state",
)
async def get_game_state(
    session_id: str,
    orchestrator: GameOrchestrator = Depends(get_orchestrator),
) -> GameState:
    """Return the latest state snapshot for a session."""

    try:
        return await orchestrator.get_state(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": str(exc)},
        ) from exc
