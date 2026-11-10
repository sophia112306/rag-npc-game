"""Transactional repository for sessions and complete game turns."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.schemas.api_response import GameTurnResponse
from backend.schemas.game_state import GameState
from backend.schemas.player_action import PlayerAction
from backend.schemas.story import ProposalDecision

from .models import (
    ActionRecord,
    CommitmentRecord,
    DialogueRecord,
    GameEventRecord,
    GameSessionRecord,
    MemoryRecord,
)


class PersistentSessionNotFoundError(LookupError):
    """Raised when a repository operation references an unknown session."""


class ActionIdConflictError(RuntimeError):
    """Raised when the same action ID is reused for different effective input."""

    def __init__(self, action_id: UUID) -> None:
        self.action_id = action_id
        super().__init__(f"Action '{action_id}' was already used with different content")


class PersistentStateVersionConflictError(RuntimeError):
    """Raised when a transaction loses the optimistic state-version race."""

    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(f"Expected state version {expected}, but the current version is {actual}")


@dataclass(frozen=True)
class CommittedGameEvent:
    """Approved event data safe to persist as an established game fact."""

    event_type: str
    description: str
    event_id: str | None = None
    actor_id: str | None = None
    target_id: str | None = None
    cause_event_id: str | None = None
    effect: dict[str, Any] | None = None
    visibility: dict[str, Any] | None = None


def effective_action_payload(action: PlayerAction) -> dict[str, Any]:
    """Return the validated request fields that determine idempotent behavior."""

    return {
        "session_id": action.session_id,
        "message": action.message,
        "input_type": action.input_type.value,
        "target_npc_id": action.target_npc_id,
        "action_mode": action.action_mode.value,
        "expected_state_version": action.expected_state_version,
    }


def action_request_digest(action: PlayerAction) -> str:
    """Hash canonical effective content while excluding transport timestamps."""

    canonical = json.dumps(
        effective_action_payload(action),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


class SqlAlchemyGameRepository:
    """Persist authoritative state and every completed turn in one transaction."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_or_get_session(self, initial_state: GameState) -> GameState:
        async with self._session_factory() as database:
            existing = await database.get(GameSessionRecord, initial_state.session_id)
            if existing is not None:
                return GameState.model_validate(existing.state_json)
            database.add(self._session_record(initial_state))
            try:
                await database.commit()
                return initial_state.model_copy(deep=True)
            except IntegrityError:
                await database.rollback()

        async with self._session_factory() as database:
            existing = await database.get(GameSessionRecord, initial_state.session_id)
            if existing is None:
                raise PersistentSessionNotFoundError(initial_state.session_id)
            return GameState.model_validate(existing.state_json)

    async def get_state(self, session_id: str) -> GameState | None:
        async with self._session_factory() as database:
            record = await database.get(GameSessionRecord, session_id)
            return GameState.model_validate(record.state_json) if record else None

    async def get_completed_action(
        self,
        session_id: str,
        action_id: UUID,
        request_digest: str,
    ) -> GameTurnResponse | None:
        async with self._session_factory() as database:
            record = await self._find_action(database, session_id, action_id)
            return self._validated_cached_response(record, action_id, request_digest)

    async def commit_turn(
        self,
        action: PlayerAction,
        request_digest: str,
        updated_state: GameState,
        response: GameTurnResponse,
        approved_events: Sequence[CommittedGameEvent] = (),
        proposal_decisions: Sequence[ProposalDecision] = (),
    ) -> GameTurnResponse:
        try:
            async with self._session_factory() as database:
                async with database.begin():
                    existing = await self._find_action(database, action.session_id, action.action_id)
                    cached = self._validated_cached_response(
                        existing,
                        action.action_id,
                        request_digest,
                    )
                    if cached is not None:
                        return cached

                    session_record = await database.get(GameSessionRecord, action.session_id)
                    if session_record is None:
                        raise PersistentSessionNotFoundError(action.session_id)
                    if session_record.state_version != action.expected_state_version:
                        raise PersistentStateVersionConflictError(
                            action.expected_state_version,
                            session_record.state_version,
                        )
                    if updated_state.state_version != action.expected_state_version + 1:
                        raise ValueError("Committed state must advance state_version exactly once")
                    if response.state.state_version != updated_state.state_version:
                        raise ValueError("Player view must represent the committed state version")

                    state_payload = updated_state.model_dump(mode="json")
                    result = await database.execute(
                        update(GameSessionRecord)
                        .where(
                            GameSessionRecord.session_id == action.session_id,
                            GameSessionRecord.state_version == action.expected_state_version,
                        )
                        .values(
                            state_version=updated_state.state_version,
                            turn_count=updated_state.turn_count,
                            state_json=state_payload,
                            updated_at=updated_state.updated_at,
                        )
                    )
                    if result.rowcount != 1:
                        current = await database.get(GameSessionRecord, action.session_id)
                        actual = current.state_version if current else action.expected_state_version
                        raise PersistentStateVersionConflictError(action.expected_state_version, actual)

                    completed_at = datetime.now(timezone.utc)
                    database.add(
                        ActionRecord(
                            session_id=action.session_id,
                            action_id=str(action.action_id),
                            request_digest=request_digest,
                            request_json={
                                "action_id": str(action.action_id),
                                **effective_action_payload(action),
                            },
                            status="completed",
                            response_json=response.model_dump(mode="json"),
                            resolution_json=[
                                decision.model_dump(mode="json") for decision in proposal_decisions
                            ],
                            error_json=None,
                            created_at=action.created_at,
                            completed_at=completed_at,
                        )
                    )
                    for position, line in enumerate(response.story.dialogue):
                        database.add(
                            DialogueRecord(
                                dialogue_id=str(uuid4()),
                                session_id=action.session_id,
                                action_id=str(action.action_id),
                                turn_number=response.turn_number,
                                position=position,
                                speaker_type=line.speaker_type.value,
                                speaker_id=line.speaker_id,
                                speaker_name=line.speaker_name,
                                text=line.text,
                                emotion=line.emotion,
                                visibility="player",
                                created_at=completed_at,
                            )
                        )
                    if (
                        action.target_npc_id is not None
                        and action.target_npc_id in updated_state.npc_states
                    ):
                        database.add(
                            MemoryRecord(
                                memory_id=str(uuid4()),
                                session_id=action.session_id,
                                npc_id=action.target_npc_id,
                                content=f"玩家說：「{action.message}」",
                                memory_type="interaction",
                                source_event_id=None,
                                source_action_id=str(action.action_id),
                                occurred_turn=response.turn_number,
                                importance=10,
                                is_active=True,
                                is_private=True,
                                provenance_json={"input_type": action.input_type.value},
                                created_at=completed_at,
                            )
                        )
                    for event in approved_events:
                        event_id = event.event_id or str(uuid4())
                        database.add(
                            GameEventRecord(
                                event_id=event_id,
                                session_id=action.session_id,
                                action_id=str(action.action_id),
                                turn_number=response.turn_number,
                                event_type=event.event_type,
                                status="established",
                                actor_id=event.actor_id,
                                target_id=event.target_id,
                                cause_event_id=event.cause_event_id,
                                description=event.description,
                                effect_json=event.effect or {},
                                visibility_json=event.visibility or {"audience": "player"},
                                created_at=completed_at,
                            )
                        )
                        witness_ids = (event.visibility or {}).get("witness_ids", [])
                        for witness_id in dict.fromkeys(witness_ids):
                            if witness_id not in updated_state.npc_states:
                                continue
                            database.add(
                                MemoryRecord(
                                    memory_id=str(uuid4()),
                                    session_id=action.session_id,
                                    npc_id=witness_id,
                                    content=event.description,
                                    memory_type="observed_event",
                                    source_event_id=event_id,
                                    source_action_id=str(action.action_id),
                                    occurred_turn=response.turn_number,
                                    importance=20,
                                    is_active=True,
                                    is_private=True,
                                    provenance_json={"event_type": event.event_type},
                                    created_at=completed_at,
                                )
                            )
                        for operation in (event.effect or {}).get("operations", []):
                            if operation.get("operation_type") != "establish_commitment":
                                continue
                            database.add(
                                CommitmentRecord(
                                    commitment_id=operation["commitment_id"],
                                    session_id=action.session_id,
                                    summary=operation["summary"],
                                    promisor_id=operation["promisor_id"],
                                    promisee_id=operation["promisee_id"],
                                    status="active",
                                    created_turn=operation["created_turn"],
                                    due_turn=operation["due_turn"],
                                    source_kind="established_event",
                                    source_id=event_id,
                                    visibility=operation["visibility"],
                                    provenance_json={
                                        "action_id": str(action.action_id),
                                        "proposal_id": operation["proposal_id"],
                                    },
                                    created_at=completed_at,
                                    updated_at=completed_at,
                                )
                            )
                    await database.flush()
                return response.model_copy(deep=True)
        except IntegrityError:
            cached = await self.get_completed_action(
                action.session_id,
                action.action_id,
                request_digest,
            )
            if cached is not None:
                return cached
            raise

    @staticmethod
    async def _find_action(
        database: AsyncSession,
        session_id: str,
        action_id: UUID,
    ) -> ActionRecord | None:
        result = await database.execute(
            select(ActionRecord).where(
                ActionRecord.session_id == session_id,
                ActionRecord.action_id == str(action_id),
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _validated_cached_response(
        record: ActionRecord | None,
        action_id: UUID,
        request_digest: str,
    ) -> GameTurnResponse | None:
        if record is None:
            return None
        if record.request_digest != request_digest:
            raise ActionIdConflictError(action_id)
        if record.status != "completed" or record.response_json is None:
            return None
        return GameTurnResponse.model_validate(record.response_json)

    @staticmethod
    def _session_record(state: GameState) -> GameSessionRecord:
        return GameSessionRecord(
            session_id=state.session_id,
            state_version=state.state_version,
            turn_count=state.turn_count,
            state_json=state.model_dump(mode="json"),
            created_at=state.created_at,
            updated_at=state.updated_at,
        )
