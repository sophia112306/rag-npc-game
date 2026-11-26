#!/usr/bin/env python3
"""Build leakage-resistant Judge train/eval JSONL from approved annotations."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from gpu_gateway.review_audit import ReviewAnnotationRecord  # noqa: E402
from gpu_gateway.semantic_review import (  # noqa: E402
    REVIEW_SYSTEM_PROMPT,
    SemanticReviewResult,
)
from scripts.validate_review_annotations import (  # noqa: E402
    validate_annotation_file,
)


def _review_input(row: ReviewAnnotationRecord) -> dict[str, object]:
    context = row.audit.context
    return {
        "player_message": row.audit.player_message,
        "adapter_draft": row.audit.adapter_draft,
        "authorized_context": {
            "npc_id": context.npc_id,
            "public_profile": context.public_profile,
            "private_behavior_guidance": context.private_behavior_guidance,
            "confirmed_knowledge": context.confirmed_knowledge,
            "recent_memories": context.authorized_memories,
            "missing_or_unconfirmed_topics": (
                context.missing_or_unconfirmed_topics
            ),
            "player_inventory": context.player_inventory,
            "allowed_objective_operations": [],
            "npc_trust": context.npc_trust,
            "npc_mode": context.npc_mode,
        },
    }


def _training_row(row: ReviewAnnotationRecord) -> dict[str, object]:
    annotation = row.annotation
    assert annotation.gold_decision is not None
    assert annotation.gold_issue is not None
    assert annotation.gold_reason is not None
    assert annotation.gold_dialogue is not None
    target = SemanticReviewResult(
        decision=annotation.gold_decision,
        issue=annotation.gold_issue,
        reason=annotation.gold_reason,
        dialogue=annotation.gold_dialogue,
        emotion=None,
    )
    return {
        "messages": [
            {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    _review_input(row),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            },
            {
                "role": "assistant",
                "content": target.model_dump_json(),
            },
        ],
        "metadata": {
            "record_id": row.audit.record_id,
            "request_fingerprint": row.audit.request_fingerprint,
            "session_hash": row.audit.session_hash,
            "npc_id": row.audit.context.npc_id,
            "annotator": annotation.annotator,
        },
    }


def _load_approved(path: Path) -> list[ReviewAnnotationRecord]:
    validate_annotation_file(path, require_approved=True)
    return [
        ReviewAnnotationRecord.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _split_by_session(
    rows: list[ReviewAnnotationRecord],
    *,
    eval_ratio: float,
    seed: str,
) -> tuple[list[ReviewAnnotationRecord], list[ReviewAnnotationRecord]]:
    by_session: dict[str, list[ReviewAnnotationRecord]] = defaultdict(list)
    for row in rows:
        by_session[row.audit.session_hash].append(row)
    if len(by_session) < 2:
        raise ValueError(
            "At least two distinct sessions are required for a leakage-free split"
        )

    ordered_sessions = sorted(
        by_session,
        key=lambda value: hashlib.sha256(
            f"{seed}:{value}".encode("utf-8")
        ).hexdigest(),
    )
    target_eval_rows = max(1, round(len(rows) * eval_ratio))
    eval_sessions: set[str] = set()
    eval_count = 0
    for session_hash in ordered_sessions[:-1]:
        if eval_count >= target_eval_rows:
            break
        eval_sessions.add(session_hash)
        eval_count += len(by_session[session_hash])

    train = [row for row in rows if row.audit.session_hash not in eval_sessions]
    evaluation = [
        row for row in rows if row.audit.session_hash in eval_sessions
    ]
    if not train or not evaluation:
        raise ValueError("Both train and eval splits must contain at least one row")
    return train, evaluation


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
        handle.flush()
        os.fsync(handle.fileno())


def build_judge_dataset(
    annotation_path: Path,
    output_dir: Path,
    *,
    eval_ratio: float = 0.2,
    seed: str = "semantic-judge-v1",
    overwrite: bool = False,
) -> dict[str, int]:
    if not 0 < eval_ratio < 1:
        raise ValueError("eval_ratio must be between zero and one")
    if output_dir.exists() and any(output_dir.iterdir()) and not overwrite:
        raise FileExistsError(
            f"Refusing to overwrite non-empty {output_dir}; pass --force"
        )
    rows = _load_approved(annotation_path)
    train, evaluation = _split_by_session(
        rows,
        eval_ratio=eval_ratio,
        seed=seed,
    )
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    _write_jsonl(output_dir / "train.jsonl", [_training_row(row) for row in train])
    _write_jsonl(
        output_dir / "eval.jsonl",
        [_training_row(row) for row in evaluation],
    )

    stats: Counter[str] = Counter(
        total=len(rows),
        train=len(train),
        eval=len(evaluation),
        train_sessions=len({row.audit.session_hash for row in train}),
        eval_sessions=len({row.audit.session_hash for row in evaluation}),
    )
    for row in rows:
        assert row.annotation.gold_issue is not None
        stats[f"issue:{row.annotation.gold_issue}"] += 1
    manifest = {
        "schema_version": 1,
        "source": str(annotation_path),
        "eval_ratio": eval_ratio,
        "split_seed": seed,
        "stats": dict(sorted(stats.items())),
    }
    descriptor = os.open(
        output_dir / "manifest.json",
        os.O_CREAT | os.O_TRUNC | os.O_WRONLY,
        0o600,
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--eval-ratio", type=float, default=0.2)
    parser.add_argument("--seed", default="semantic-judge-v1")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    stats = build_judge_dataset(
        args.annotations,
        args.output_dir,
        eval_ratio=args.eval_ratio,
        seed=args.seed,
        overwrite=args.force,
    )
    print(f"OK {args.output_dir}: {json.dumps(stats, sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
