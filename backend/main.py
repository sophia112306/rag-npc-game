"""FastAPI application entry point for the RAG NPC game backend."""

from fastapi import FastAPI

from .api.health import APP_VERSION, SERVICE_NAME, router as health_router


app = FastAPI(
    title="RAG NPC Game API",
    description="Backend API for the RAG NPC game.",
    version=APP_VERSION,
)

app.include_router(health_router)


@app.get("/", tags=["meta"], summary="Show API service information")
def read_root() -> dict[str, str]:
    """Return basic service information without touching external services."""

    return {
        "service": SERVICE_NAME,
        "version": APP_VERSION,
        "docs": "/docs",
    }
