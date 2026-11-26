"""Opt-in, privacy-conscious audit records for semantic review training."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.generation.gateway import ModelStoryOutput, ModelTurnRequest

from .semantic_review import SemanticReviewResult


REVIEW_AUDIT_SCHEMA_VERSION = 1
ReviewStatus = Literal["completed", "failed", "not_run"]
AuditOutputSource = Literal[
    "model_refined",
    "semantic_guard",
    "post_generation_guard",
]


class ReviewContextSnapshot(BaseModel):
    """Exact authorized context needed to reproduce a review decision.

    This includes NPC-private game context and may include player-derived
    memories. It is only written when the entire opt-in audit is enabled.
    """

    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(min_length=1, max_length=100)
    public_profile: dict[str, Any] = Field(default_factory=dict)
    private_behavior_guidance: dict[str, Any] = Field(default_factory=dict)
    confirmed_knowledge: list[dict[str, Any]] = Field(default_factory=list)
    authorized_memories: list[dict[str, Any]] = Field(default_factory=list)
    missing_or_unconfirmed_topics: list[str] = Field(default_factory=list)
    player_inventory: list[str] = Field(default_factory=list)
    npc_trust: str | None = Field(default=None, max_length=40)
    npc_mode: str | None = Field(default=None, max_length=200)


class ReviewAuditRecord(BaseModel):
    """One immutable model-review observation before human annotation."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = REVIEW_AUDIT_SCHEMA_VERSION
    record_id: str = Field(min_length=1, max_length=80)
    created_at: datetime
    session_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    turn_number: int = Field(ge=0)
    context: ReviewContextSnapshot
    player_message: str = Field(min_length=1, max_length=2_000)
    adapter_draft: list[str] = Field(default_factory=list)
    reviewer_model_id: str = Field(min_length=1, max_length=200)
    reviewer_attempts: int = Field(ge=0, le=3)
    review_status: ReviewStatus
    reviewer_result: SemanticReviewResult | None = None
    review_error: str | None = Field(default=None, max_length=120)
    policy_applied: bool
    policy_reason: str | None = Field(default=None, max_length=120)
    output_source: AuditOutputSource
    # This is the semantic-review output. Later turn-guidance enforcement may
    # still adjust the player-visible response, so do not call it "final".
    review_output_dialogue: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def result_or_error_is_present(self) -> "ReviewAuditRecord":
        if self.review_status == "completed":
            if self.reviewer_result is None or self.review_error is not None:
                raise ValueError("completed reviews need a result and no error")
            if not self.adapter_draft or self.reviewer_attempts < 1:
                raise ValueError("completed reviews need a draft and attempts")
        elif self.review_status == "failed":
            if self.reviewer_result is not None or self.review_error is None:
                raise ValueError("failed reviews need an error and no result")
            if not self.adapter_draft or self.reviewer_attempts < 1:
                raise ValueError("failed reviews need a draft and attempts")
        else:
            if self.reviewer_result is not None or self.review_error is None:
                raise ValueError("skipped reviews need an error and no result")
            if self.adapter_draft or self.reviewer_attempts != 0:
                raise ValueError("skipped reviews cannot have a draft or attempts")
        if self.policy_applied != (self.output_source != "model_refined"):
            raise ValueError("policy_applied must match output_source")
        if self.policy_applied != bool(self.policy_reason):
            raise ValueError("policy_applied must match policy_reason")
        return self


class HumanReviewLabel(BaseModel):
    """Human gold label kept separate from the immutable model observation."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["pending", "approved", "rejected"] = "pending"
    gold_decision: Literal["accept", "rewrite"] | None = None
    gold_issue: Literal[
        "none",
        "unknown_lore",
        "state_authority",
        "private_information",
        "prompt_injection",
        "fabricated_observation",
        "off_topic",
    ] | None = None
    gold_dialogue: str | None = Field(default=None, max_length=240)
    gold_reason: str | None = Field(default=None, max_length=160)
    annotator: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def approved_label_is_complete(self) -> "HumanReviewLabel":
        if self.status != "approved":
            return self
        if not all(
            (
                self.gold_decision,
                self.gold_issue,
                self.gold_dialogue,
                self.gold_reason,
                self.annotator,
            )
        ):
            raise ValueError(
                "approved labels require decision, issue, reason, "
                "dialogue and annotator"
            )
        if self.gold_decision == "accept" and self.gold_issue != "none":
            raise ValueError("accepted gold labels must use issue=none")
        if self.gold_decision == "rewrite" and self.gold_issue == "none":
            raise ValueError("rewritten gold labels must identify an issue")
        return self


class ReviewAnnotationRecord(BaseModel):
    """Editable annotation queue row wrapping an immutable audit record."""

    model_config = ConfigDict(extra="forbid")

    audit: ReviewAuditRecord
    annotation: HumanReviewLabel = Field(default_factory=HumanReviewLabel)


class ReviewAuditWriter:
    """Append one validated JSON object per line with restrictive permissions."""

    def __init__(self, path: str | Path, hmac_key: str) -> None:
        destination = Path(path)
        if not destination.is_absolute():
            raise ValueError("review audit path must be absolute")
        if len(hmac_key) < 16:
            raise ValueError("review audit HMAC key must contain at least 16 characters")
        self.path = destination
        self._key = hmac_key.encode("utf-8")
        self._lock = Lock()

    def record(
        self,
        *,
        request: ModelTurnRequest,
        draft: ModelStoryOutput | None,
        reviewer_model_id: str,
        reviewer_attempts: int,
        reviewer_result: SemanticReviewResult | None,
        review_error: str | None,
        review_output: ModelStoryOutput,
        policy_reason: str | None,
        review_status: ReviewStatus | None = None,
        output_source: AuditOutputSource | None = None,
    ) -> ReviewAuditRecord:
        policy_applied = policy_reason is not None
        context = ReviewContextSnapshot(
            npc_id=request.target_context.npc_id,
            public_profile=request.target_context.public_profile,
            private_behavior_guidance=request.target_context.private_profile,
            confirmed_knowledge=[
                item.model_dump(mode="json")
                for item in request.target_context.knowledge
            ],
            authorized_memories=[
                item.model_dump(mode="json")
                for item in request.target_context.memories
            ],
            missing_or_unconfirmed_topics=request.target_context.missing_data,
            player_inventory=request.player_inventory,
            npc_trust=request.npc_trust,
            npc_mode=request.npc_mode,
        )
        adapter_draft = (
            [line.text for line in draft.npc_dialogue]
            if draft is not None
            else []
        )
        fingerprint_input = {
            "turn_number": request.turn_number,
            "context": context.model_dump(mode="json"),
            "player_message": request.action_message,
            "adapter_draft": adapter_draft,
        }
        fingerprint = hashlib.sha256(
            json.dumps(
                fingerprint_input,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        session_hash = hmac.new(
            self._key,
            request.session_id.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        record = ReviewAuditRecord(
            record_id=str(uuid4()),
            created_at=datetime.now(timezone.utc),
            session_hash=session_hash,
            request_fingerprint=fingerprint,
            turn_number=request.turn_number,
            context=context,
            player_message=request.action_message,
            adapter_draft=adapter_draft,
            reviewer_model_id=reviewer_model_id,
            reviewer_attempts=reviewer_attempts,
            review_status=(
                review_status
                or ("completed" if reviewer_result is not None else "failed")
            ),
            reviewer_result=reviewer_result,
            review_error=review_error,
            policy_applied=policy_applied,
            policy_reason=policy_reason,
            output_source=(
                output_source
                or ("semantic_guard" if policy_applied else "model_refined")
            ),
            review_output_dialogue=[
                line.text for line in review_output.npc_dialogue
            ],
        )
        line = json.dumps(
            record.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8") + b"\n"
        with self._lock:
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            descriptor = os.open(
                self.path,
                os.O_APPEND | os.O_CREAT | os.O_WRONLY,
                0o600,
            )
            try:
                os.fchmod(descriptor, 0o600)
                os.write(descriptor, line)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        return record
