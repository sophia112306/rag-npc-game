"""FastAPI application entry point for the RAG NPC game backend."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.content.characters import CHARACTER_DEFINITIONS
from backend.content.context_repository import NPCContextRepository
from backend.database import create_async_session_factory, create_database_engine, upgrade_database
from backend.database.session import get_database_url
from backend.database.repository import SqlAlchemyGameRepository
from backend.generation.config import build_story_planner_from_env
from backend.orchestration.game_orchestrator import GameOrchestrator, StoryPlanner

from .api.characters import router as character_router
from .api.game import router as game_router
from .api.health import APP_VERSION, SERVICE_NAME, router as health_router


StoryPlannerFactory = Callable[[NPCContextRepository], StoryPlanner]


def create_app(
    database_url: str | None = None,
    story_planner_factory: StoryPlannerFactory | None = None,
) -> FastAPI:
    """Build an application with an isolated persistence lifecycle."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        resolved_database_url = database_url or get_database_url()
        await upgrade_database(resolved_database_url)
        engine = create_database_engine(resolved_database_url)
        session_factory = create_async_session_factory(engine)
        repository = SqlAlchemyGameRepository(session_factory)
        context_repository = NPCContextRepository(session_factory)
        for definition in CHARACTER_DEFINITIONS.values():
            await context_repository.ensure_character_definition(definition)
        story_planner = (
            story_planner_factory(context_repository)
            if story_planner_factory
            else build_story_planner_from_env(context_repository)
        )
        application.state.database_engine = engine
        application.state.game_orchestrator = GameOrchestrator(repository, story_planner=story_planner)
        application.state.npc_context_repository = context_repository
        try:
            yield
        finally:
            await engine.dispose()

    application = FastAPI(
        title="RAG NPC Game API",
        description="Backend API for the RAG NPC game.",
        version=APP_VERSION,
        lifespan=lifespan,
    )

    allowed_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3200,http://127.0.0.1:3200",
        ).split(",")
        if origin.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    application.include_router(health_router)
    application.include_router(character_router)
    application.include_router(game_router)

    @application.get("/", tags=["meta"], summary="Show API service information")
    def read_root() -> dict[str, str]:
        """Return basic service information without touching external services."""

        return {
            "service": SERVICE_NAME,
            "version": APP_VERSION,
            "docs": "/docs",
        }

    return application


app = create_app()
