"""FastAPI application entry point for the RAG NPC game backend."""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.characters import router as character_router
from .api.game import router as game_router
from .api.health import APP_VERSION, SERVICE_NAME, router as health_router


app = FastAPI(
    title="RAG NPC Game API",
    description="Backend API for the RAG NPC game.",
    version=APP_VERSION,
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:3200,http://127.0.0.1:3200",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(health_router)
app.include_router(character_router)
app.include_router(game_router)


@app.get("/", tags=["meta"], summary="Show API service information")
def read_root() -> dict[str, str]:
    """Return basic service information without touching external services."""

    return {
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
    }
