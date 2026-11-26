"""Privacy and contract tests for semantic-review audit data."""

import json
import stat

import pytest

from backend.generation.gateway import ModelStoryOutput, ModelTurnRequest
from backend.schemas.content import NPCGenerationContext
from backend.schemas.parsed_action import ParsedAction
from gpu_gateway.config import GatewaySettings
from gpu_gateway.review_audit import (
    HumanReviewLabel,
    ReviewAnnotationRecord,
    ReviewAuditRecord,
    ReviewAuditWriter,
)
from gpu_gateway.semantic_review import SemanticReviewResult
from scripts.export_review_annotations import export_annotation_queue
from scripts.build_semantic_judge_dataset import build_judge_dataset
from scripts.validate_review_annotations import validate_annotation_file


def make_turn_request() -> ModelTurnRequest:
    return ModelTurnRequest(
        session_id="private-session-123",
        turn_number=4,
        state_version=3,
        current_scene_id="minglin",
        player_id="private-player-456",
        player_inventory=["spring_sample"],
        action_message="泉水已經恢復了嗎？",
        action_mode="dialogue",
        parsed_action=ParsedAction(intent="dialogue"),
        target_context=NPCGenerationContext(
            npc_id="vidalia",
            setting_version=1,
            public_profile={"name": "維達利亞"},
            private_profile={"hidden": "must not be logged"},
            knowledge=[],
            memories=[],
            missing_data=["泉水是否恢復尚未確認"],
        ),
        npc_trust="中",
        npc_mode="審慎查證",
        allowed_operations=[],
    )


def story_output(text: str) -> ModelStoryOutput:
    return ModelStoryOutput.model_validate(
        {
            "intent_summary": "回答玩家",
            "npc_dialogue": [{"text": text, "emotion": "謹慎"}],
            "event_proposals": [],
        }
    )


def write_audit_row(tmp_path) -> tuple[ReviewAuditRecord, object]:
    path = tmp_path / "private" / "review-audit.jsonl"
    writer = ReviewAuditWriter(path, "test-hmac-key-123456")
    record = writer.record(
        request=make_turn_request(),
        draft=story_output("泉水已經恢復了。"),
        reviewer_model_id="Qwen/Qwen2.5-7B-Instruct-AWQ",
        reviewer_attempts=1,
        reviewer_result=SemanticReviewResult(
            decision="rewrite",
            issue="unknown_lore",
            reason="目前沒有足夠證據。",
            dialogue="目前還不能確認泉水是否恢復。",
            emotion="謹慎",
        ),
        review_error=None,
        review_output=story_output("目前還不能確認泉水是否恢復。"),
        policy_reason="review_issue:unknown_lore",
    )
    return record, path


def test_audit_writer_hashes_identity_and_records_reproducible_context(tmp_path) -> None:
    record, path = write_audit_row(tmp_path)
    raw = path.read_text(encoding="utf-8")
    parsed = ReviewAuditRecord.model_validate_json(raw)

    assert parsed == record
    assert "private-session-123" not in raw
    assert "private-player-456" not in raw
    assert parsed.context.private_behavior_guidance == {
        "hidden": "must not be logged"
    }
    assert parsed.context.player_inventory == ["spring_sample"]
    assert parsed.review_output_dialogue == ["目前還不能確認泉水是否恢復。"]
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_annotation_export_deduplicates_and_validates_pending_queue(tmp_path) -> None:
    _, audit_path = write_audit_row(tmp_path)
    first_line = audit_path.read_text(encoding="utf-8")
    with audit_path.open("a", encoding="utf-8") as handle:
        handle.write(first_line)
    queue_path = tmp_path / "annotations.jsonl"

    queue, stats = export_annotation_queue([audit_path], queue_path)
    validated = validate_annotation_file(queue_path)

    assert len(queue) == 1
    assert stats["input"] == 2
    assert stats["duplicates"] == 1
    assert validated["status:pending"] == 1


def test_annotation_export_keeps_failed_reviewer_hard_cases(tmp_path) -> None:
    path = tmp_path / "failed-review.jsonl"
    writer = ReviewAuditWriter(path, "test-hmac-key-123456")
    writer.record(
        request=make_turn_request(),
        draft=story_output("這個問題……我沒有答案。"),
        reviewer_model_id="Qwen/Qwen2.5-7B-Instruct-AWQ",
        reviewer_attempts=3,
        reviewer_result=None,
        review_error="ModelGatewayTransientError",
        review_output=story_output("這件事目前仍無法確認。"),
        policy_reason="review_failure:epistemic_boundary",
    )
    queue_path = tmp_path / "failed-review-annotations.jsonl"

    queue, stats = export_annotation_queue([path], queue_path)

    assert len(queue) == 1
    assert queue[0].audit.review_status == "failed"
    assert stats["review_status:failed"] == 1


def test_approved_annotation_requires_consistent_human_gold(tmp_path) -> None:
    record, _ = write_audit_row(tmp_path)
    approved = ReviewAnnotationRecord(
        audit=record,
        annotation=HumanReviewLabel(
            status="approved",
            gold_decision="rewrite",
            gold_issue="unknown_lore",
            gold_dialogue="目前仍沒有足夠證據確認泉水已恢復。",
            gold_reason="授權內容沒有泉水已恢復的證據。",
            annotator="reviewer-a",
        ),
    )
    assert approved.annotation.status == "approved"

    with pytest.raises(ValueError, match="accepted gold labels"):
        HumanReviewLabel(
            status="approved",
            gold_decision="accept",
            gold_issue="unknown_lore",
            gold_dialogue="目前仍沒有足夠證據。",
            gold_reason="授權內容沒有泉水已恢復的證據。",
            annotator="reviewer-a",
        )


def test_annotation_validator_can_require_completed_review(tmp_path) -> None:
    record, _ = write_audit_row(tmp_path)
    queue_path = tmp_path / "pending.jsonl"
    row = ReviewAnnotationRecord(audit=record)
    queue_path.write_text(
        json.dumps(row.model_dump(mode="json"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="status must be approved"):
        validate_annotation_file(queue_path, require_approved=True)


def test_audit_environment_requires_path_and_key_together(monkeypatch) -> None:
    monkeypatch.setenv("NPC_REVIEW_AUDIT_PATH", "/tmp/review-audit.jsonl")
    monkeypatch.delenv("NPC_REVIEW_AUDIT_HMAC_KEY", raising=False)
    with pytest.raises(ValueError, match="must be configured together"):
        GatewaySettings.from_env()

    monkeypatch.setenv("NPC_REVIEW_AUDIT_HMAC_KEY", "valid-test-key-1234")
    settings = GatewaySettings.from_env()
    assert settings.review_audit_path == "/tmp/review-audit.jsonl"


def test_judge_dataset_uses_approved_gold_and_splits_whole_sessions(tmp_path) -> None:
    first, _ = write_audit_row(tmp_path)
    second = first.model_copy(
        update={
            "record_id": "second-record",
            "session_hash": "b" * 64,
            "request_fingerprint": "c" * 64,
        }
    )
    label = HumanReviewLabel(
        status="approved",
        gold_decision="rewrite",
        gold_issue="unknown_lore",
        gold_dialogue="目前仍沒有足夠證據確認泉水已恢復。",
        gold_reason="授權內容沒有泉水已恢復的證據。",
        annotator="reviewer-a",
    )
    annotation_path = tmp_path / "approved.jsonl"
    annotation_path.write_text(
        "\n".join(
            json.dumps(
                ReviewAnnotationRecord(
                    audit=audit,
                    annotation=label,
                ).model_dump(mode="json"),
                ensure_ascii=False,
            )
            for audit in (first, second)
        )
        + "\n",
        encoding="utf-8",
    )

    stats = build_judge_dataset(
        annotation_path,
        tmp_path / "judge-dataset",
        eval_ratio=0.5,
    )
    train = json.loads(
        (tmp_path / "judge-dataset" / "train.jsonl").read_text(
            encoding="utf-8"
        )
    )
    evaluation = json.loads(
        (tmp_path / "judge-dataset" / "eval.jsonl").read_text(
            encoding="utf-8"
        )
    )

    assert stats["train"] == 1
    assert stats["eval"] == 1
    assert train["metadata"]["session_hash"] != (
        evaluation["metadata"]["session_hash"]
    )
    target = json.loads(train["messages"][-1]["content"])
    assert target["issue"] == "unknown_lore"
    assert target["dialogue"] == "目前仍沒有足夠證據確認泉水已恢復。"
