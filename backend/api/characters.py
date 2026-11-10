"""Player-visible character endpoints."""

from fastapi import APIRouter, HTTPException, status

from backend.content.characters import CHARACTER_PROFILES
from backend.schemas.character import CharacterProfile


router = APIRouter(prefix="/api/characters", tags=["characters"])


@router.get("/{npc_id}", response_model=CharacterProfile, summary="Get a public character profile")
def get_character(npc_id: str) -> CharacterProfile:
    """Return only public profile fields, never private NPC knowledge or secrets."""

    profile = CHARACTER_PROFILES.get(npc_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "CHARACTER_NOT_FOUND", "message": f"Character '{npc_id}' does not exist"},
        )
    return profile
