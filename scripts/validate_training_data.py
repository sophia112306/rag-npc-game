#!/usr/bin/env python3
"""Validate NPC training JSONL against the runtime ModelStoryOutput schema."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT_DIR = Path(__file__).resolve().parent.parent
TRAINING_DATASETS = {
    "andre": "npc_train_andre.jsonl",
    "dasso": "npc_train_dhaso.jsonl",
    "menmesvento": "menmesvento_data.jsonl",
    "seth": "npc_train_seth.jsonl",
    "syra": "npc_train_syra.jsonl",
    "vidalia": "vidalia_train.jsonl",
}
sys.path.insert(0, str(ROOT_DIR))

from backend.generation.gateway import ModelStoryOutput  # noqa: E402


def main() -> int:
    total = 0
    for npc_id, filename in TRAINING_DATASETS.items():
        path = ROOT_DIR / "training" / "data" / filename
        count = 0
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            messages = row["messages"]
            if messages[-1]["role"] != "assistant":
                raise ValueError(f"{path}:{line_number}: assistant target must be last")
            target = json.loads(messages[-1]["content"])
            ModelStoryOutput.model_validate(target)
            if target["event_proposals"]:
                raise ValueError(
                    f"{path}:{line_number}: persona samples must not teach trusted events"
                )
            count += 1
        print(f"OK {path.relative_to(ROOT_DIR)}: {count} rows")
        total += count
    if not total:
        raise ValueError("No training rows found")
    print(f"OK total: {total} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
