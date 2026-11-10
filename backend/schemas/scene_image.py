"""Player-safe contracts for post-commit scene image work."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SceneImageJobStatus = Literal["queued", "processing", "succeeded", "fallback"]


class EnqueueSceneImageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_state_version: int = Field(..., ge=1)


class SceneImageJobView(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    job_id: str
    session_id: str
    scene_id: str
    story_node_id: str
    state_version: int
    prompt_fingerprint: str
    provider: str
    status: SceneImageJobStatus
    image_url: str | None
    attempt_count: int
    error_code: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
