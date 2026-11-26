#!/usr/bin/env python3
"""Export validated semantic-review audit rows into a human annotation queue."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
from pathlib import Path
import sys
from typing import Iterable


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from gpu_gateway.review_audit import (  # noqa: E402
    HumanReviewLabel,
    ReviewAnnotationRecord,
    ReviewAuditRecord,
)


def read_audit_records(paths: Iterable[Path]) -> list[ReviewAuditRecord]:
    records: list[ReviewAuditRecord] = []
    for path in paths:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            1,
        ):
            if not line.strip():
                continue
            try:
                records.append(ReviewAuditRecord.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: invalid audit row") from exc
    return records


def export_annotation_queue(
    source_paths: Iterable[Path],
    output_path: Path,
    *,
    overwrite: bool = False,
) -> tuple[list[ReviewAnnotationRecord], Counter[str]]:
    if output_path.exists() and not overwrite:
        raise FileExistsError(
            f"Refusing to overwrite {output_path}; pass --force to replace it"
        )

    stats: Counter[str] = Counter()
    queue: list[ReviewAnnotationRecord] = []
    seen_fingerprints: set[str] = set()
    for audit in read_audit_records(source_paths):
        stats["input"] += 1
        stats[f"review_status:{audit.review_status}"] += 1
        if audit.request_fingerprint in seen_fingerprints:
            stats["duplicates"] += 1
            continue
        seen_fingerprints.add(audit.request_fingerprint)
        # A failed reviewer still has a valid NPC draft and is a valuable
        # hard case for human correction. Only pre-draft failures cannot train
        # the Judge and stay out of the annotation queue.
        if audit.review_status == "not_run":
            stats["not_run_skipped"] += 1
            continue
        queue.append(
            ReviewAnnotationRecord(
                audit=audit,
                annotation=HumanReviewLabel(),
            )
        )
        stats["exported"] += 1
        stats[f"source:{audit.output_source}"] += 1
        if audit.reviewer_result is not None:
            stats[f"issue:{audit.reviewer_result.issue}"] += 1
        if audit.policy_reason:
            stats[f"policy:{audit.policy_reason}"] += 1

    output_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_CREAT | os.O_WRONLY | os.O_TRUNC
    descriptor = os.open(output_path, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        for row in queue:
            handle.write(
                json.dumps(
                    row.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
        handle.flush()
        os.fsync(handle.fileno())
    return queue, stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        action="append",
        required=True,
        help="audit JSONL path; repeat for multiple files",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    queue, stats = export_annotation_queue(
        args.source,
        args.output,
        overwrite=args.force,
    )
    print(f"OK {args.output}: {len(queue)} pending annotation rows")
    print(json.dumps(dict(sorted(stats.items())), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
