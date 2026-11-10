"""Player-visible character profile contracts."""

from pydantic import BaseModel, ConfigDict, Field


class CharacterProfile(BaseModel):
    """Public, immutable character information safe to expose to the client."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    npc_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    romanized_name: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    scene_name: str = Field(..., min_length=1, max_length=200)
    portrait_url: str = Field(..., min_length=1, max_length=500)
    description: str = Field(..., min_length=1, max_length=1_000)
    greeting: str = Field(..., min_length=1, max_length=2_000)
