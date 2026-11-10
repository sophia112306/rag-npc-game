"""FastAPI application entry point for the RAG NPC game backend."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import create_async_session_factory, create_database_engine, upgrade_database
from backend.database.session import get_database_url
from backend.database.repository import SqlAlchemyGameRepository
from backend.orchestration.game_orchestrator import GameOrchestrator

from .api.characters import router as character_router
from .api.game import router as game_router
from .api.health import APP_VERSION, SERVICE_NAME, router as health_router


def create_app(database_url: str | None = None) -> FastAPI:
    """Build an application with an isolated persistence lifecycle."""

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        resolved_database_url = database_url or get_database_url()
        await upgrade_database(resolved_database_url)
        engine = create_database_engine(resolved_database_url)
        repository = SqlAlchemyGameRepository(create_async_session_factory(engine))
        application.state.database_engine = engine
        application.state.game_orchestrator = GameOrchestrator(repository)
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
