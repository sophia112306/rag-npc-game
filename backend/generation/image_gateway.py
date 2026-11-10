"""Provider-neutral scene image generation boundary."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SceneImageRequest:
    job_id: str
    scene_id: str
    story_node_id: str
    prompt: str


@dataclass(frozen=True)
class SceneImageResult:
    image_url: str


class ImageGateway(Protocol):
    """Adapter implemented by a hosted image API or an internal GPU service."""

    @property
    def provider_name(self) -> str: ...

    async def generate(self, request: SceneImageRequest) -> SceneImageResult: ...
