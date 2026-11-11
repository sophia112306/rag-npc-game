"""Private Hunyuan adapter and durable, single-worker scene asset generation."""

import asyncio
import base64
from datetime import datetime, timezone
from hashlib import sha256
import json
import logging
import os
from pathlib import Path
import struct
from typing import Protocol
from uuid import uuid4

import httpx
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from backend.content.world_scenes import build_world_scene, default_config
from backend.database.models import SceneAssetJobRecord
from backend.schemas.game_state import GameState
from backend.schemas.world_scene import AssetKind, SceneAssetJobView

LOGGER = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = PROJECT_ROOT / "frontend/public/game/models/references"
ASSET_KINDS: tuple[AssetKind, ...] = ("tree", "runestone", "altar")


def validate_glb(raw: bytes) -> None:
    """Reject HTML, oversized models and GLBs with remote dependencies."""
    if len(raw) < 24 or len(raw) > 8 * 1024 * 1024:
        raise ValueError("GLB_SIZE_INVALID")
    magic, version, length = struct.unpack_from("<4sII", raw)
    if magic != b"glTF" or version != 2 or length != len(raw):
        raise ValueError("GLB_HEADER_INVALID")
    size, kind = struct.unpack_from("<II", raw, 12)
    if kind != 0x4E4F534A or size > len(raw) - 20:
        raise ValueError("GLB_JSON_INVALID")
    document = json.loads(raw[20 : 20 + size])
    if any(
        "uri" in item for key in ("buffers", "images") for item in document.get(key, [])
    ):
        raise ValueError("GLB_EXTERNAL_RESOURCE")
    primitives = [
        p for mesh in document.get("meshes", []) for p in mesh.get("primitives", [])
    ]
    if not primitives:
        raise ValueError("GLB_MESH_MISSING")
    accessors = document.get("accessors", [])
    triangles = sum(
        accessors[p["indices"]]["count"] // 3
        if "indices" in p
        else accessors[p["attributes"]["POSITION"]]["count"] // 3
        for p in primitives
    )
    if triangles > 100_000:
        raise ValueError("GLB_FACE_LIMIT")


class SceneAssetGateway(Protocol):
    async def generate(self, kind: AssetKind, seed: int) -> bytes: ...


class HunyuanAssetGateway:
    def __init__(self, url: str):
        self.url = url.rstrip("/")

    async def generate(self, kind: AssetKind, seed: int) -> bytes:
        image = await asyncio.to_thread((REFERENCE_ROOT / f"{kind}-v1.png").read_bytes)
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(150, connect=5), trust_env=False
        ) as client:
            async with client.stream(
                "POST",
                f"{self.url}/generate",
                json={
                    "image": base64.b64encode(image).decode(),
                    "seed": seed,
                    "octree_resolution": 256,
                    "num_inference_steps": 5,
                    "max_faces": 20_000,
                },
            ) as response:
                response.raise_for_status()
                chunks = bytearray()
                async for chunk in response.aiter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 8 * 1024 * 1024:
                        raise ValueError("GLB_SIZE_INVALID")
        raw = bytes(chunks)
        validate_glb(raw)
        return raw


class SceneAssetCoordinator:
    """Recover queued work on restart. Claim once, retry at most twice, retain GLBs."""

    def __init__(
        self,
        session_factory,
        gateway: SceneAssetGateway | None,
        output_dir: Path | None = None,
    ):
        self.sessions = session_factory
        self.gateway = gateway
        self.output_dir = output_dir or PROJECT_ROOT / "data/generated_assets"
        self.wake = asyncio.Event()
        self.task: asyncio.Task | None = None

    async def start(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # A single app worker owns this queue; interrupted claims are safe to repeat.
        async with self.sessions() as db:
            await db.execute(
                update(SceneAssetJobRecord)
                .where(SceneAssetJobRecord.status == "processing")
                .values(status="queued")
            )
            await db.commit()
            await db.execute(
                update(SceneAssetJobRecord)
                .where(
                    SceneAssetJobRecord.status == "queued",
                    SceneAssetJobRecord.attempt_count >= 2,
                )
                .values(status="fallback", error_code="ATTEMPTS_EXHAUSTED")
            )
            await db.commit()
        if self.gateway:
            self.task = asyncio.create_task(self._worker())
        else:
            async with self.sessions() as db:
                await db.execute(
                    update(SceneAssetJobRecord)
                    .where(SceneAssetJobRecord.status == "queued")
                    .values(status="fallback", error_code="HUNYUAN_UNCONFIGURED")
                )
                await db.commit()

    async def close(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def enqueue(self, state: GameState) -> list[SceneAssetJobView]:
        world = build_world_scene(
            state.current_scene_id, state.world_scenes.get(state.current_scene_id)
        )
        kinds = sorted({obj.kind for obj in world.objects if not obj.protected})
        needs_new_geometry = (
            world.config.seed != default_config(state.current_scene_id).seed
        )
        generate = self.gateway is not None and needs_new_geometry
        jobs = []
        for kind in kinds:
            reference = REFERENCE_ROOT / f"{kind}-v1.png"
            ref_hash = (
                sha256(reference.read_bytes()).hexdigest()
                if reference.is_file()
                else "missing"
            )
            fingerprint = sha256(
                f"shape-textured-v2:{kind}:{world.config.seed}:{ref_hash}".encode()
            ).hexdigest()
            async with self.sessions() as db:
                query = select(SceneAssetJobRecord).where(
                    SceneAssetJobRecord.session_id == state.session_id,
                    SceneAssetJobRecord.fingerprint == fingerprint,
                )
                row = (await db.execute(query)).scalar_one_or_none()
                if row is None:
                    fallback_url = f"/game/models/{kind}-v1.glb"
                    row = SceneAssetJobRecord(
                        job_id=str(uuid4()),
                        session_id=state.session_id,
                        scene_id=state.current_scene_id,
                        kind=kind,
                        seed=world.config.seed,
                        fingerprint=fingerprint,
                        status="queued" if generate else "fallback",
                        fallback_url=fallback_url,
                        model_url=None if generate else fallback_url,
                        attempt_count=0,
                        error_code="HUNYUAN_UNCONFIGURED"
                        if needs_new_geometry and not self.gateway
                        else None,
                    )
                    db.add(row)
                    try:
                        await db.commit()
                    except IntegrityError:
                        await db.rollback()
                        row = (await db.execute(query)).scalar_one()
                elif (
                    generate
                    and row.status == "fallback"
                    and row.error_code == "HUNYUAN_UNCONFIGURED"
                ):
                    row.status = "queued"
                    row.error_code = None
                    row.model_url = None
                    await db.commit()
                jobs.append(SceneAssetJobView.model_validate(row))
        self.wake.set()
        return jobs

    async def get(self, session_id: str, job_id: str) -> SceneAssetJobView | None:
        async with self.sessions() as db:
            row = await db.get(SceneAssetJobRecord, job_id)
            if row is None or row.session_id != session_id:
                return None
            return SceneAssetJobView.model_validate(row)

    async def _worker(self):
        while True:
            try:
                async with self.sessions() as db:
                    row = (
                        await db.execute(
                            select(SceneAssetJobRecord)
                            .where(SceneAssetJobRecord.status == "queued")
                            .order_by(SceneAssetJobRecord.created_at)
                            .limit(1)
                        )
                    ).scalar_one_or_none()
                    job_id = row.job_id if row else None
                if job_id:
                    await self.process(job_id)
                    continue
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=1)
                except TimeoutError:
                    pass
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("Scene asset worker recovered from an error")
                await asyncio.sleep(1)

    async def process(self, job_id: str):
        if not self.gateway:
            return
        async with self.sessions() as db:
            result = await db.execute(
                update(SceneAssetJobRecord)
                .where(
                    SceneAssetJobRecord.job_id == job_id,
                    SceneAssetJobRecord.status == "queued",
                )
                .values(
                    status="processing",
                    attempt_count=SceneAssetJobRecord.attempt_count + 1,
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await db.commit()
            if result.rowcount != 1:
                return
            row = await db.get(SceneAssetJobRecord, job_id)
            kind, seed, attempt = row.kind, row.seed, row.attempt_count
        error = None
        try:
            raw = await self.gateway.generate(kind, seed)
            validate_glb(raw)
            temporary = self.output_dir / f"{job_id}.partial"
            await asyncio.to_thread(temporary.write_bytes, raw)
            await asyncio.to_thread(
                os.replace, temporary, self.output_dir / f"{job_id}.glb"
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            error = type(exc).__name__
            LOGGER.warning("Scene asset %s failed: %s", job_id, error)
        async with self.sessions() as db:
            row = await db.get(SceneAssetJobRecord, job_id)
            if error:
                row.status = "queued" if attempt < 2 else "fallback"
                row.error_code = error
                row.model_url = row.fallback_url if attempt >= 2 else None
            else:
                row.status = "succeeded"
                row.error_code = None
                row.model_url = (
                    f"/api/game/{row.session_id}/scene-assets/{row.job_id}/model"
                )
            row.updated_at = datetime.now(timezone.utc)
            await db.commit()
        if error and attempt < 2:
            await asyncio.sleep(2)
