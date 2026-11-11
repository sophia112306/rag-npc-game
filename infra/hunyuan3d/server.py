"""Private, shape-only Hunyuan3D gateway for the school GPU host.

The service deliberately omits CORS and texture generation. It is intended to
listen inside the container and be published only on the remote loopback
interface by Docker Compose, then reached through an SSH tunnel.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import logging
import os
import uuid
from contextlib import asynccontextmanager
from io import BytesIO
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

LOGGER = logging.getLogger("hunyuan3d_gateway")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

MODEL_ID = os.getenv("HUNYUAN3D_MODEL", "tencent/Hunyuan3D-2mini")
MODEL_SUBFOLDER = os.getenv(
    "HUNYUAN3D_SUBFOLDER", "hunyuan3d-dit-v2-mini-turbo"
)
OUTPUT_DIR = Path(os.getenv("HUNYUAN3D_OUTPUT_DIR", "/outputs"))
MAX_INPUT_BYTES = int(os.getenv("HUNYUAN3D_MAX_INPUT_BYTES", str(12 * 1024 * 1024)))
MAX_IMAGE_PIXELS = int(os.getenv("HUNYUAN3D_MAX_IMAGE_PIXELS", "24000000"))
UPSTREAM_COMMIT = os.getenv("HUNYUAN3D_UPSTREAM_COMMIT", "unknown")


class GenerateRequest(BaseModel):
    image: str = Field(description="Base64-encoded PNG, JPEG or WebP image")
    seed: int = Field(default=1234, ge=0, le=2**31 - 1)
    octree_resolution: Literal[128, 256] = 256
    num_inference_steps: int = Field(default=5, ge=1, le=30)
    guidance_scale: float = Field(default=5.0, ge=0.0, le=20.0)


class RuntimeState:
    status: Literal["loading", "ready", "error"] = "loading"
    error: str | None = None
    device_name: str | None = None
    torch_version: str | None = None
    pipeline: Any = None
    background_remover: Any = None
    load_task: asyncio.Task[None] | None = None


RUNTIME = RuntimeState()
GENERATION_LOCK = asyncio.Lock()


def _load_runtime() -> None:
    import torch
    from hy3dgen.rembg import BackgroundRemover
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available inside the container")

    RUNTIME.device_name = torch.cuda.get_device_name(0)
    RUNTIME.torch_version = torch.__version__
    LOGGER.info("Loading %s/%s on %s", MODEL_ID, MODEL_SUBFOLDER, RUNTIME.device_name)
    RUNTIME.background_remover = BackgroundRemover()
    RUNTIME.pipeline = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        MODEL_ID,
        subfolder=MODEL_SUBFOLDER,
        use_safetensors=True,
        device="cuda",
    )
    # Do not call enable_flashvdm here. The upstream optimization compiles
    # extra CUDA code and is not required for the first Blackwell-safe demo.


async def _initialize_runtime() -> None:
    try:
        await asyncio.to_thread(_load_runtime)
    except Exception as exc:  # pragma: no cover - exercised on the GPU host
        RUNTIME.status = "error"
        RUNTIME.error = f"{type(exc).__name__}: {exc}"
        LOGGER.exception("Hunyuan3D initialization failed")
    else:
        RUNTIME.status = "ready"
        LOGGER.info("Hunyuan3D is ready")


@asynccontextmanager
async def lifespan(_: FastAPI):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME.load_task = asyncio.create_task(_initialize_runtime())
    yield
    if RUNTIME.load_task and not RUNTIME.load_task.done():
        RUNTIME.load_task.cancel()


app = FastAPI(
    title="RAG NPC Hunyuan3D Gateway",
    version="0.1.0",
    lifespan=lifespan,
)


def _decode_image(encoded: str) -> Image.Image:
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="image must be valid base64") from exc

    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"image must be between 1 and {MAX_INPUT_BYTES} bytes",
        )

    try:
        image = Image.open(BytesIO(raw))
        if image.format not in {"PNG", "JPEG", "WEBP"}:
            raise HTTPException(status_code=415, detail="image must be PNG, JPEG or WebP")
        width, height = image.size
        if width * height > MAX_IMAGE_PIXELS:
            raise HTTPException(status_code=413, detail="image has too many pixels")
        image.load()
        return image.convert("RGBA")
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(status_code=415, detail="image cannot be decoded") from exc


def _generate_mesh(request: GenerateRequest, image: Image.Image, output_path: Path) -> None:
    import torch

    processed = RUNTIME.background_remover(image)
    generator = torch.Generator(device="cuda").manual_seed(request.seed)
    mesh = RUNTIME.pipeline(
        image=processed,
        generator=generator,
        octree_resolution=request.octree_resolution,
        num_inference_steps=request.num_inference_steps,
        guidance_scale=request.guidance_scale,
        mc_algo="mc",
    )[0]
    mesh.export(output_path)
    torch.cuda.empty_cache()


@app.get("/live")
async def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health")
async def health() -> dict[str, str | None]:
    return {
        "status": RUNTIME.status,
        "model": MODEL_ID,
        "subfolder": MODEL_SUBFOLDER,
        "device": RUNTIME.device_name,
        "torch_version": RUNTIME.torch_version,
        "upstream_commit": UPSTREAM_COMMIT,
        "error": RUNTIME.error,
    }


@app.post("/generate", response_class=FileResponse)
async def generate(request: GenerateRequest) -> FileResponse:
    if RUNTIME.status == "error":
        raise HTTPException(status_code=503, detail=RUNTIME.error or "model failed to load")
    if RUNTIME.status != "ready":
        raise HTTPException(status_code=503, detail="model is still loading")
    if GENERATION_LOCK.locked():
        raise HTTPException(status_code=429, detail="one generation is already running")

    image = _decode_image(request.image)
    output_path = OUTPUT_DIR / f"{uuid.uuid4()}.glb"
    async with GENERATION_LOCK:
        try:
            await asyncio.to_thread(_generate_mesh, request, image, output_path)
        except RuntimeError as exc:
            LOGGER.exception("Hunyuan3D generation failed")
            raise HTTPException(status_code=500, detail="generation failed") from exc

    return FileResponse(
        output_path,
        media_type="model/gltf-binary",
        filename=output_path.name,
        headers={"X-Hunyuan3D-Model": MODEL_ID},
    )
