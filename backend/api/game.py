"""Game endpoints exposed to the frontend."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from backend.generation.planner import StoryGenerationUnavailableError
from backend.orchestration.game_orchestrator import (
    ActionIdConflictError,
    GameOrchestrator,
    SessionNotFoundError,
    StateVersionConflictError,
    StoryChoiceMismatchError,
    StoryChoiceUnavailableError,
)
from backend.schemas.api_response import GameTurnResponse
from backend.schemas.player_action import PlayerAction
from backend.schemas.player_choice import PlayerChoice
from backend.schemas.player_view import PlayerViewState, project_player_view
from backend.schemas.progression import PlayerQuestView


class StartGameRequest(BaseModel):
    """Request body used to create or resume a game session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=100)


router = APIRouter(prefix="/api/game", tags=["game"])


def get_orchestrator(request: Request) -> GameOrchestrator:
    """Return the database-backed orchestrator configured by the app lifespan."""

    return request.app.state.game_orchestrator


@router.post(
    "/start",
    response_model=PlayerViewState,
    status_code=status.HTTP_201_CREATED,
    summary="Start a game session",
)
async def start_game(
    request: StartGameRequest,
    orchestrator: GameOrchestrator = Depends(get_orchestrator),
) -> PlayerViewState:
    """Create a new session or return the existing session state."""

    state = await orchestrator.start_game(request.session_id)
    return project_player_view(state)


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
    except StateVersionConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "STATE_VERSION_CONFLICT",
                "message": str(exc),
                "expected_state_version": exc.expected,
                "actual_state_version": exc.actual,
            },
        ) from exc
    except ActionIdConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ACTION_ID_CONFLICT",
                "message": str(exc),
                "action_id": str(exc.action_id),
            },
        ) from exc
    except StoryChoiceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "STORY_CHOICE_UNAVAILABLE", "message": str(exc)},
        ) from exc
    except StoryChoiceMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "STORY_CHOICE_MISMATCH", "message": str(exc)},
        ) from exc
    except StoryGenerationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "STORY_GENERATION_UNAVAILABLE",
                "message": str(exc),
                "reason": exc.code,
                "attempts": exc.attempts,
            },
            headers={"Retry-After": "2"},
        ) from exc


@router.get(
    "/{session_id}/choices",
    response_model=list[PlayerChoice],
    summary="Get player-visible action choices",
)
async def get_player_choices(
    session_id: str,
    orchestrator: GameOrchestrator = Depends(get_orchestrator),
) -> list[PlayerChoice]:
    """Return clickable choices derived from the current public session state."""

    try:
        return await orchestrator.get_player_choices(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": str(exc)},
        ) from exc


@router.get(
    "/{session_id}/quests",
    response_model=list[PlayerQuestView],
    summary="Get player-visible open quests",
)
async def get_player_quests(
    session_id: str,
    orchestrator: GameOrchestrator = Depends(get_orchestrator),
) -> list[PlayerQuestView]:
    try:
        return await orchestrator.get_player_quests(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": str(exc)},
        ) from exc


@router.get(
    "/{session_id}/state",
    response_model=PlayerViewState,
    summary="Get the current game state",
)
async def get_game_state(
    session_id: str,
    orchestrator: GameOrchestrator = Depends(get_orchestrator),
) -> PlayerViewState:
    """Return the latest state snapshot for a session."""

    try:
        state = await orchestrator.get_state(session_id)
        return project_player_view(state)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": str(exc)},
        ) from exc
