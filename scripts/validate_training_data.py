#!/usr/bin/env python3
"""Validate NPC training JSONL against the runtime ModelStoryOutput schema."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.generation.gateway import ModelStoryOutput  # noqa: E402
from scripts.migrate_training_data_to_model_story_output import (  # noqa: E402
    DATASET_FILENAMES,
)


def validate_data_dir(data_dir: Path) -> tuple[int, int]:
    total_rows = 0
    total_targets = 0
    for npc_id, filename in DATASET_FILENAMES.items():
        path = data_dir / filename
        row_count = 0
        target_count = 0
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(),
            1,
        ):
            if not line.strip():
                continue
            row = json.loads(line)
            messages = row.get("messages")
            if not isinstance(messages, list) or not messages:
                raise ValueError(
                    f"{path}:{line_number}: messages must be a non-empty list"
                )
            if messages[0].get("role") != "system":
                raise ValueError(
                    f"{path}:{line_number}: system message must be first"
                )
            if messages[-1].get("role") != "assistant":
                raise ValueError(
                    f"{path}:{line_number}: assistant target must be last"
                )
            if "ModelStoryOutput" not in str(messages[0].get("content", "")):
                raise ValueError(
                    f"{path}:{line_number}: system prompt lacks output contract"
                )
            assistant_messages = [
                message
                for message in messages
                if message.get("role") == "assistant"
            ]
            if not assistant_messages:
                raise ValueError(
                    f"{path}:{line_number}: no assistant target"
                )
            for message_index, message in enumerate(assistant_messages, 1):
                try:
                    target = json.loads(message["content"])
                    ModelStoryOutput.model_validate(target)
                except (KeyError, TypeError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"{path}:{line_number}: invalid assistant target "
                        f"{message_index}"
                    ) from exc
                if target["event_proposals"]:
                    raise ValueError(
                        f"{path}:{line_number}: persona samples must not "
                        "teach trusted events"
                    )
                target_count += 1
            row_count += 1
        print(
            f"OK {path}: {row_count} rows, "
            f"{target_count} assistant targets"
        )
        total_rows += row_count
        total_targets += target_count
    if not total_rows:
        raise ValueError("No training rows found")
    print(
        f"OK total: {total_rows} rows, "
        f"{total_targets} assistant targets"
    )
    return total_rows, total_targets


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=ROOT_DIR / "training" / "data",
        help="directory containing all eight dataset filenames",
    )
    args = parser.parse_args()
    validate_data_dir(args.data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
