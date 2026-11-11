"""Bounded, public scene composition; separate from immutable story canon."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AssetKind = Literal["tree", "runestone", "altar"]


class WorldSceneConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(default=0, ge=0)
    seed: int = Field(default=1234, ge=0, le=2**31 - 1)
    weather: Literal["clear", "mist", "rain", "dust"] = "clear"
    time_of_day: Literal["day", "dusk", "night"] = "day"
    terrain: Literal["rolling", "dunes", "rocky"] = "rolling"
    tree_count: int = Field(default=24, ge=0, le=48)
    runestone_count: int = Field(default=4, ge=0, le=12)
    altar_count: int = Field(default=1, ge=0, le=3)


class WorldObject(BaseModel):
    kind: AssetKind
    object_id: str
    x: float
    z: float
    scale: float
    yaw: float


class WorldSceneView(BaseModel):
    scene_id: str
    config: WorldSceneConfig
    objects: list[WorldObject]
    spawn_x: float = 0
    spawn_z: float = 8
    interaction_x: float = 0
    interaction_z: float = -6
    interaction_label: str
    npc_id: str | None = None
    water: bool = False
    fire: bool = False


class SceneAssetJobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    scene_id: str
    kind: AssetKind
    seed: int
    status: Literal["queued", "processing", "succeeded", "fallback"]
    model_url: str | None
    fallback_url: str
    error_code: str | None
    attempt_count: int


class EnqueueSceneAssetsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state_version: int = Field(ge=1)
