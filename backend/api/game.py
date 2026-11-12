"""Game endpoints exposed to the frontend."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from backend.generation.planner import StoryGenerationUnavailableError
from backend.generation.scene_image_jobs import (
    SceneImageCoordinator,
    SceneImageJobNotFoundError,
)
from backend.orchestration.game_orchestrator import (
    ActionIdConflictError,
    GameOrchestrator,
    SessionNotFoundError,
    StateVersionConflictError,
    StoryChoiceMismatchError,
    StoryChoiceUnavailableError,
    NpcUnavailableError,
)
from backend.schemas.api_response import GameTurnResponse
from backend.schemas.player_action import PlayerAction
from backend.schemas.player_choice import PlayerChoice
from backend.schemas.player_view import PlayerViewState, project_player_view
from backend.schemas.progression import PlayerQuestView
from backend.schemas.scene_image import EnqueueSceneImageRequest, SceneImageJobView
from backend.orchestration.world_commands import UnsupportedWorldCommand


class StartGameRequest(BaseModel):
    """Request body used to create or resume a game session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=100)


router = APIRouter(prefix="/api/game", tags=["game"])


def get_orchestrator(request: Request) -> GameOrchestrator:
    """Return the database-backed orchestrator configured by the app lifespan."""

    return request.app.state.game_orchestrator


def get_scene_image_coordinator(request: Request) -> SceneImageCoordinator:
    return request.app.state.scene_image_coordinator


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
    except UnsupportedWorldCommand as exc:
        raise HTTPException(status_code=422, detail={"code": "UNSUPPORTED_WORLD_COMMAND", "message": str(exc)}) from exc
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
    except NpcUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "NPC_UNAVAILABLE", "message": str(exc)},
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
    npc_id: Literal["vidalia", "andre", "menmesvento", "dasso", "seth", "syra"] | None = None,
    orchestrator: GameOrchestrator = Depends(get_orchestrator),
) -> list[PlayerChoice]:
    """Return clickable choices derived from the current public session state."""

    try:
        return await orchestrator.get_player_choices(session_id, npc_id)
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


@router.post(
    "/{session_id}/scene-image",
    response_model=SceneImageJobView,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue the current public scene image",
)
async def enqueue_scene_image(
    session_id: str,
    request: EnqueueSceneImageRequest,
    background_tasks: BackgroundTasks,
    orchestrator: GameOrchestrator = Depends(get_orchestrator),
    coordinator: SceneImageCoordinator = Depends(get_scene_image_coordinator),
) -> SceneImageJobView:
    """Create a deduplicated image job only after the state is committed."""

    try:
        state = await orchestrator.get_state(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SESSION_NOT_FOUND", "message": str(exc)},
        ) from exc
    if request.expected_state_version != state.state_version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "STATE_VERSION_CONFLICT",
                "message": "Scene image request does not match the current state version.",
                "expected_state_version": request.expected_state_version,
                "actual_state_version": state.state_version,
            },
        )

    job = await coordinator.enqueue(state)
    if job.status == "queued":
        background_tasks.add_task(coordinator.process, job.job_id)
    return job


@router.get(
    "/{session_id}/scene-image/{job_id}",
    response_model=SceneImageJobView,
    summary="Get scene image job status",
)
async def get_scene_image_job(
    session_id: str,
    job_id: str,
    coordinator: SceneImageCoordinator = Depends(get_scene_image_coordinator),
) -> SceneImageJobView:
    try:
        return await coordinator.get_job(session_id, job_id)
    except SceneImageJobNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "SCENE_IMAGE_JOB_NOT_FOUND", "message": str(exc)},
        ) from exc
