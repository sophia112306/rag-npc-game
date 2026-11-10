"""Persistent post-commit scene image job coordinator."""

from datetime import datetime, timezone
from hashlib import sha256
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.content.scenes import require_scene
from backend.database.models import SceneImageJobRecord
from backend.schemas.game_state import GameState
from backend.schemas.scene_image import SceneImageJobView

from .image_gateway import ImageGateway, SceneImageRequest


class SceneImageJobNotFoundError(LookupError):
    pass


class SceneImageCoordinator:
    """Enqueue after a committed turn and process outside the turn transaction."""

    STYLE_VERSION = "vita-painterly-environment-v1"

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        gateway: ImageGateway | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._gateway = gateway

    async def enqueue(self, state: GameState) -> SceneImageJobView:
        scene = require_scene(state.current_scene_id)
        prompt = self._build_prompt(state)
        fingerprint = sha256(
            json.dumps(
                {
                    "style": self.STYLE_VERSION,
                    "scene_id": scene.scene_id,
                    "story_node_id": state.story_progress.node_id,
                    "public_clue_ids": sorted(state.story_progress.public_clue_ids),
                    "prompt": prompt,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        async with self._session_factory() as database:
            existing = await self._find_by_fingerprint(
                database,
                state.session_id,
                fingerprint,
            )
            if existing is not None:
                return SceneImageJobView.model_validate(existing)

            now = datetime.now(timezone.utc)
            fallback = self._gateway is None
            record = SceneImageJobRecord(
                job_id=str(uuid4()),
                session_id=state.session_id,
                scene_id=scene.scene_id,
                story_node_id=state.story_progress.node_id,
                state_version=state.state_version,
                prompt_fingerprint=fingerprint,
                prompt_text=prompt,
                provider=self._gateway.provider_name if self._gateway else "static_fallback",
                status="fallback" if fallback else "queued",
                fallback_url=scene.horizon_url,
                image_url=scene.horizon_url if fallback else None,
                attempt_count=0,
                error_code="IMAGE_GATEWAY_UNCONFIGURED" if fallback else None,
                created_at=now,
                updated_at=now,
                completed_at=now if fallback else None,
            )
            database.add(record)
            try:
                await database.commit()
                return SceneImageJobView.model_validate(record)
            except IntegrityError:
                await database.rollback()
                existing = await self._find_by_fingerprint(
                    database,
                    state.session_id,
                    fingerprint,
                )
                if existing is None:
                    raise
                return SceneImageJobView.model_validate(existing)

    async def get_job(self, session_id: str, job_id: str) -> SceneImageJobView:
        async with self._session_factory() as database:
            result = await database.execute(
                select(SceneImageJobRecord).where(
                    SceneImageJobRecord.job_id == job_id,
                    SceneImageJobRecord.session_id == session_id,
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                raise SceneImageJobNotFoundError(job_id)
            return SceneImageJobView.model_validate(record)

    async def process(self, job_id: str) -> None:
        if self._gateway is None:
            return

        async with self._session_factory() as database:
            record = await database.get(SceneImageJobRecord, job_id)
            if record is None or record.status not in {"queued", "processing"}:
                return
            record.status = "processing"
            record.attempt_count += 1
            record.updated_at = datetime.now(timezone.utc)
            request = SceneImageRequest(
                job_id=record.job_id,
                scene_id=record.scene_id,
                story_node_id=record.story_node_id,
                prompt=record.prompt_text,
            )
            await database.commit()

        try:
            result = await self._gateway.generate(request)
            if not result.image_url:
                raise ValueError("Image gateway returned an empty image URL")
        except Exception as exc:
            async with self._session_factory() as database:
                record = await database.get(SceneImageJobRecord, job_id)
                if record is None:
                    return
                now = datetime.now(timezone.utc)
                record.status = "fallback"
                record.image_url = record.fallback_url
                record.error_code = type(exc).__name__
                record.updated_at = now
                record.completed_at = now
                await database.commit()
            return

        async with self._session_factory() as database:
            record = await database.get(SceneImageJobRecord, job_id)
            if record is None:
                return
            now = datetime.now(timezone.utc)
            record.status = "succeeded"
            record.image_url = result.image_url
            record.error_code = None
            record.updated_at = now
            record.completed_at = now
            await database.commit()

    @staticmethod
    async def _find_by_fingerprint(
        database: AsyncSession,
        session_id: str,
        fingerprint: str,
    ) -> SceneImageJobRecord | None:
        result = await database.execute(
            select(SceneImageJobRecord).where(
                SceneImageJobRecord.session_id == session_id,
                SceneImageJobRecord.prompt_fingerprint == fingerprint,
            )
        )
        return result.scalar_one_or_none()

    @classmethod
    def _build_prompt(cls, state: GameState) -> str:
        scene = require_scene(state.current_scene_id)
        clues = ", ".join(sorted(state.story_progress.public_clue_ids)) or "none"
        return (
            f"Style guide: {cls.STYLE_VERSION}. "
            f"Create a 16:9 environment-only game scene for {scene.display_name} "
            f"({scene.subtitle}). Public description: {scene.description}. "
            f"Current public story chapter: {state.story_progress.chapter_title}. "
            f"Revealed public clue IDs: {clues}. "
            "No text, UI, portrait, private NPC memory, hidden setting, or unrevealed secret."
        )
