"""Relational persistence models for sessions and complete game turns."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
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
