"""Training-data bridge tests for the eight NPC LoRA datasets."""

import json
from pathlib import Path

from scripts.migrate_training_data_to_model_story_output import (
    DATASET_FILENAMES,
    DATA_DIR,
    _convert_target,
    migrate_file,
)
from scripts.validate_training_data import validate_data_dir


def _message(role: str, content: str) -> dict[str, str]:
    return {"role": role, "content": content}


def test_convert_target_accepts_every_author_output_shape() -> None:
    plain = _convert_target("先確認親眼所見的痕跡。")
    legacy = _convert_target(
        json.dumps(
            {"relation_delta": 1, "line": "我會先聽完雙方證詞。"},
            ensure_ascii=False,
        )
    )
    structured = _convert_target(
        json.dumps(
            {
                "intent_summary": "回應玩家。",
                "npc_dialogue": [
                    {"text": "先查證。", "emotion": "calm"}
                ],
                "event_proposals": [
                    {
                        "event_type": "untrusted",
                    }
                ],
            },
            ensure_ascii=False,
        )
    )

    assert plain["npc_dialogue"][0]["text"] == "先確認親眼所見的痕跡。"
    assert legacy["npc_dialogue"][0]["text"] == "我會先聽完雙方證詞。"
    assert structured["npc_dialogue"][0]["text"] == "先查證。"
    assert plain["event_proposals"] == []
    assert legacy["event_proposals"] == []
    assert structured["event_proposals"] == []


def test_migration_preserves_context_and_converts_every_assistant(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.jsonl"
    destination = tmp_path / "normalized.jsonl"
    row = {
        "messages": [
            _message(
                "system",
                "你是遊戲 NPC，只輸出台詞。\n"
                "角色：安德烈\n場景：鳴霖邊界\n信任度：中",
            ),
            _message("user", "你先看見了什麼？"),
            _message("assistant", "我先看見地上的裂痕。"),
            _message("user", "接著呢？"),
            _message(
                "assistant",
                '{"relation_delta":0,"line":"再比對兩份證詞。"}',
            ),
        ]
    }
    original = json.dumps(row, ensure_ascii=False) + "\n"
    source.write_text(original, encoding="utf-8")

    assert migrate_file(
        source,
        "andre",
        check=False,
        destination=destination,
    )
    assert source.read_text(encoding="utf-8") == original

    normalized = json.loads(destination.read_text(encoding="utf-8"))
    system_prompt = normalized["messages"][0]["content"]
    assert "ModelStoryOutput" in system_prompt
    assert "場景：鳴霖邊界" in system_prompt
    assert "信任度：中" in system_prompt
    assistants = [
        json.loads(message["content"])
        for message in normalized["messages"]
        if message["role"] == "assistant"
    ]
    assert [row["npc_dialogue"][0]["text"] for row in assistants] == [
        "我先看見地上的裂痕。",
        "再比對兩份證詞。",
    ]
    assert not migrate_file(destination, "andre", check=True)


def test_all_author_datasets_export_and_validate_without_rewriting_sources(
    tmp_path: Path,
) -> None:
    expected_rows = 0
    expected_targets = 0
    for npc_id, filename in DATASET_FILENAMES.items():
        source = DATA_DIR / filename
        source_text = source.read_text(encoding="utf-8")
        for line in source_text.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            expected_rows += 1
            expected_targets += sum(
                message.get("role") == "assistant"
                for message in row["messages"]
            )
        migrate_file(
            source,
            npc_id,
            check=False,
            destination=tmp_path / filename,
        )
        assert source.read_text(encoding="utf-8") == source_text

    assert validate_data_dir(tmp_path) == (
        expected_rows,
        expected_targets,
    )
    assert set(path.name for path in tmp_path.glob("*.jsonl")) == set(
        DATASET_FILENAMES.values()
    )
