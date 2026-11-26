#!/usr/bin/env python3
"""Validate semantic-review annotation JSONL before dataset generation."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from gpu_gateway.review_audit import ReviewAnnotationRecord  # noqa: E402


def validate_annotation_file(
    path: Path,
    *,
    require_approved: bool = False,
) -> Counter[str]:
    stats: Counter[str] = Counter()
    record_ids: set[str] = set()
    fingerprints: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        1,
    ):
        if not line.strip():
            continue
        try:
            row = ReviewAnnotationRecord.model_validate_json(line)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_number}: invalid annotation row") from exc
        if row.audit.record_id in record_ids:
            raise ValueError(
                f"{path}:{line_number}: duplicate record_id {row.audit.record_id}"
            )
        if row.audit.request_fingerprint in fingerprints:
            raise ValueError(
                f"{path}:{line_number}: duplicate request_fingerprint"
            )
        record_ids.add(row.audit.record_id)
        fingerprints.add(row.audit.request_fingerprint)
        status = row.annotation.status
        stats["total"] += 1
        stats[f"status:{status}"] += 1
        if require_approved and status != "approved":
            raise ValueError(
                f"{path}:{line_number}: annotation status must be approved"
            )
        if row.annotation.gold_issue:
            stats[f"gold_issue:{row.annotation.gold_issue}"] += 1
    if not stats["total"]:
        raise ValueError(f"{path}: no annotation rows found")
    return stats


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--require-approved", action="store_true")
    args = parser.parse_args()

    stats = validate_annotation_file(
        args.data,
        require_approved=args.require_approved,
    )
    details = ", ".join(
        f"{key}={value}" for key, value in sorted(stats.items())
    )
    print(f"OK {args.data}: {details}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
