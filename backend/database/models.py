"""Relational persistence models for sessions and complete game turns."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


def utc_now() -> datetime:
    """Return a timezone-aware timestamp for application-created records."""

    return datetime.now(timezone.utc)


class GameSessionRecord(Base):
    """Latest authoritative state snapshot for one game session."""

    __tablename__ = "game_sessions"

    session_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False)
    state_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class ActionRecord(Base):
    """Idempotency record and complete serialized result for one player action."""

    __tablename__ = "action_records"
    __table_args__ = (
        UniqueConstraint("session_id", "action_id", name="uq_action_records_session_action"),
        Index("ix_action_records_session_created", "session_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("game_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    action_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    request_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    resolution_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    error_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class GameEventRecord(Base):
    """One backend-approved event produced by a committed turn."""

    __tablename__ = "game_events"
    __table_args__ = (Index("ix_game_events_session_turn", "session_id", "turn_number"),)

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("game_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    action_id: Mapped[str] = mapped_column(String(36), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cause_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    effect_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    visibility_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class DialogueRecord(Base):
    """Player-visible dialogue or narration saved with a committed turn."""

    __tablename__ = "dialogue_records"
    __table_args__ = (
        UniqueConstraint("session_id", "action_id", "position", name="uq_dialogue_turn_position"),
        Index("ix_dialogue_records_session_turn", "session_id", "turn_number"),
    )

    dialogue_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("game_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    action_id: Mapped[str] = mapped_column(String(36), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker_type: Mapped[str] = mapped_column(String(20), nullable=False)
    speaker_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    speaker_name: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    emotion: Mapped[str | None] = mapped_column(String(50), nullable=True)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="player")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class WorldCanonRecord(Base):
    """Versioned author-layer fact that generation cannot directly rewrite."""

    __tablename__ = "world_canon"
    __table_args__ = (Index("ix_world_canon_disclosure_status", "disclosure_scope", "status"),)

    canon_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    source_locator: Mapped[str | None] = mapped_column(String(500), nullable=True)
    certainty: Mapped[str] = mapped_column(String(30), nullable=False)
    disclosure_scope: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    setting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class CharacterDefinitionRecord(Base):
    """Separate public profile data from private and incomplete author settings."""

    __tablename__ = "character_definitions"

    npc_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    public_profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    private_profile_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sources_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    setting_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completeness_status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class KnowledgeRecord(Base):
    """A sourced fact, belief, or hearsay item available to one NPC."""

    __tablename__ = "knowledge_records"
    __table_args__ = (
        Index(
            "ix_knowledge_records_authorized_context",
            "session_id",
            "knower_npc_id",
            "is_unlocked",
            "available_from_turn",
        ),
    )

    knowledge_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("game_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    knower_npc_id: Mapped[str] = mapped_column(String(100), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    epistemic_status: Mapped[str] = mapped_column(String(30), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    acquired_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    available_from_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    is_unlocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disclosure_scope: Mapped[str] = mapped_column(String(30), nullable=False)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class MemoryRecord(Base):
    """Sourced episodic memory belonging to one NPC in one session."""

    __tablename__ = "memory_records"
    __table_args__ = (
        Index("ix_memory_records_npc_turn", "session_id", "npc_id", "occurred_turn"),
    )

    memory_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("game_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    npc_id: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    memory_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_event_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_action_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    occurred_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class NPCGoalRecord(Base):
    """A sourced, session-scoped NPC objective eligible for turn-clock review."""

    __tablename__ = "npc_goals"
    __table_args__ = (
        Index("ix_npc_goals_due", "session_id", "npc_id", "status", "next_review_turn"),
    )

    goal_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("game_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    npc_id: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    next_review_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class CommitmentRecord(Base):
    """A sourced promise or obligation that can influence later turns."""

    __tablename__ = "commitments"
    __table_args__ = (
        Index("ix_commitments_active", "session_id", "status", "created_turn"),
    )

    commitment_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("game_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    promisor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    promisee_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    due_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class QuestRecord(Base):
    """A sourced dynamic task offered to or accepted by one recipient."""

    __tablename__ = "quests"
    __table_args__ = (
        Index("ix_quests_open", "session_id", "recipient_id", "status", "created_turn"),
    )

    quest_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("game_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    giver_id: Mapped[str] = mapped_column(String(100), nullable=False)
    recipient_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_turn: Mapped[int] = mapped_column(Integer, nullable=False)
    due_turn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False)
    provenance_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class SceneImageJobRecord(Base):
    """A post-commit image job derived only from player-visible story state."""

    __tablename__ = "scene_image_jobs"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "prompt_fingerprint",
            name="uq_scene_image_jobs_session_fingerprint",
        ),
        Index("ix_scene_image_jobs_session_created", "session_id", "created_at"),
    )

    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("game_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    scene_id: Mapped[str] = mapped_column(String(100), nullable=False)
    story_node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    fallback_url: Mapped[str] = mapped_column(String(500), nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
