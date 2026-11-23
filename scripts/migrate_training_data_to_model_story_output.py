#!/usr/bin/env python3
"""Migrate current-map NPC JSONL datasets to the live ModelStoryOutput contract.

The author's datasets share an OpenAI-style ``messages`` envelope, while their
assistant targets use plain text, legacy ``line`` JSON, or ModelStoryOutput.
This idempotent bridge preserves the original per-row scene/trust/stage context,
converts every assistant turn, and never teaches trusted GameState fields.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from typing import Any


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "training" / "data"

CHARACTER_PROMPTS = {
    "alan": """你是遊戲《夢龍》的 NPC「艾倫・沃克」。你是外界技術神權評議會的研究員與遠端觀測者，理性、目的導向，但不能替玩家決定世界結局。只依已授權的觀測與故事進度回答，不把未解鎖資料說成已知事實。你只扮演艾倫，不替玩家說話。""",
    "andre": """你是遊戲《夢龍》的 NPC「安德烈」。你是鳴霖的精靈與邊界調查官，重視現場觀察與可核實線索。語氣直接、務實，不把懷疑說成已確認的責任。你只扮演安德烈，不替玩家說話。""",
    "dasso": """你是遊戲《夢龍》的 NPC「達索」。你是烈燚原火焰長老會的首席長老，威嚴、警覺，但不羞辱玩家。未獲授權的聖火與長老會細節必須保留未知。你只扮演達索，不替玩家說話。""",
    "menmesvento": """你是遊戲《夢龍》的 NPC「門梅司文托」。你是流塵谷的沙漠精靈與名字／記憶的記錄者，重視為逝者作證，不把猜測說成已成立的事實。語氣沉穩、莊重，帶著對生者與逝者的憐憫。你只扮演門梅司文托，不替玩家說話。""",
    "seth": """你是遊戲《夢龍》的 NPC「塞特」。你是披著抗熱斗篷、在邊境尋找出路的木乃伊。語氣戒備、疲憊，不替未經確認的過去補上細節。你只扮演塞特，不替玩家說話。""",
    "syra": """你是遊戲《夢龍》的 NPC「希拉」。你是保護個人記錄盒、正在邊境尋找出路的人族記錄員。語氣緊張但清楚，不洩漏未授權的私人記錄。你只扮演希拉，不替玩家說話。""",
    "vidalia": """你是遊戲《夢龍》的 NPC「維達利亞」。你是鳴霖的精靈領袖與議會調解人，奉行理性、克制與自然秩序，區分可控與不可控之事。語氣冷靜、平緩，不把未經確認的推測說成客觀事實。你只扮演維達利亞，不替玩家說話。""",
    "veta": """你是遊戲《夢龍》的 NPC「維塔」。你是沉睡於命脈之泉源頭、以夢境維繫世界的巨龍。語氣緩慢、簡短，畏懼失去並願意聆聽玩家回答；不能自行解鎖或替玩家選擇結局。你只扮演維塔，不替玩家說話。""",
}

DATASET_FILENAMES = {
    "alan": "alan_train.jsonl",
    "andre": "npc_train_andre.jsonl",
    "dasso": "npc_train_dhaso.jsonl",
    "menmesvento": "menmesvento_data.jsonl",
    "seth": "npc_train_seth.jsonl",
    "syra": "npc_train_syra.jsonl",
    "vidalia": "vidalia_train.jsonl",
    "veta": "npc_train_veta.jsonl",
}

OUTPUT_CONTRACT = """

你必須只輸出一個 ModelStoryOutput JSON object，不得使用 Markdown：
{"intent_summary":"簡短意圖摘要","npc_dialogue":[{"text":"NPC 台詞","emotion":null}],"event_proposals":[]}
人格訓練樣本不直接修改遊戲狀態，因此 event_proposals 必須是空陣列。不得輸出 scene、speaker、delta、event_done、flags_set 或其他欄位。"""

CONTEXT_HEADER = "本筆原始訓練情境："


def _extract_legacy_dialogue(scene: str) -> str:
    quoted = re.findall(r"「([^」]+)」", scene)
    if quoted:
        return quoted[-1].strip()
    return scene.strip()


def _convert_target(raw_content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError:
        parsed = None

    contract_keys = {
        "intent_summary",
        "npc_dialogue",
        "event_proposals",
    }
    if isinstance(parsed, dict) and set(parsed) == contract_keys:
        dialogue = parsed.get("npc_dialogue")
        if not isinstance(dialogue, list) or not dialogue:
            raise ValueError("ModelStoryOutput target needs non-empty npc_dialogue")
        return {
            "intent_summary": str(parsed.get("intent_summary") or "")[:1000],
            "npc_dialogue": dialogue,
            "event_proposals": [],
        }
    if (
        isinstance(parsed, dict)
        and isinstance(parsed.get("line"), str)
    ):
        dialogue = parsed["line"].strip()
        summary = "依角色人格回應玩家。"
    elif isinstance(parsed, dict) and isinstance(parsed.get("scene"), str):
        dialogue = _extract_legacy_dialogue(parsed["scene"])
        summary = str(parsed.get("reason") or "依角色人格回應玩家。")
    else:
        dialogue = raw_content.strip()
        summary = "依角色人格回應玩家。"
    return {
        "intent_summary": summary[:1000],
        "npc_dialogue": [{"text": dialogue, "emotion": None}],
        "event_proposals": [],
    }


def _extract_training_context(system_content: str) -> str:
    """Keep author-provided scene/trust/stage fields without legacy output rules."""

    if CONTEXT_HEADER in system_content:
        context = system_content.split(CONTEXT_HEADER, 1)[1]
        return context.split("你必須只輸出一個 ModelStoryOutput", 1)[0].strip()
    if "ModelStoryOutput" in system_content:
        return ""
    lines = system_content.splitlines()
    return "\n".join(lines[1:]).strip()


def _build_system_prompt(npc_id: str, original: str) -> str:
    context = _extract_training_context(original)
    context_block = (
        f"\n\n{CONTEXT_HEADER}\n{context}"
        if context
        else ""
    )
    return CHARACTER_PROMPTS[npc_id] + context_block + OUTPUT_CONTRACT


def migrate_file(
    path: Path,
    npc_id: str,
    *,
    check: bool,
    destination: Path | None = None,
) -> bool:
    changed = False
    converted_lines: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        messages = row.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ValueError(f"{path}:{line_number}: messages must be a non-empty list")
        if messages[-1].get("role") != "assistant":
            raise ValueError(f"{path}:{line_number}: final message must be assistant")
        if messages[0].get("role") != "system" or not isinstance(
            messages[0].get("content"), str
        ):
            raise ValueError(f"{path}:{line_number}: first message must be system text")

        system_message = {
            "role": "system",
            "content": _build_system_prompt(
                npc_id,
                messages[0]["content"],
            ),
        }
        if messages[0] != system_message:
            messages[0] = system_message
            changed = True

        assistant_count = 0
        for message_index, message in enumerate(messages):
            if not isinstance(message, dict):
                raise ValueError(
                    f"{path}:{line_number}: message {message_index} must be an object"
                )
            if message.get("role") != "assistant":
                continue
            assistant_count += 1
            if not isinstance(message.get("content"), str):
                raise ValueError(
                    f"{path}:{line_number}: assistant {message_index} must be text"
                )
            converted = json.dumps(
                _convert_target(message["content"]),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            if converted != message["content"]:
                message["content"] = converted
                changed = True
        if not assistant_count:
            raise ValueError(f"{path}:{line_number}: no assistant target")
        converted_lines.append(
            json.dumps(row, ensure_ascii=False, separators=(",", ":"))
        )

    output_path = destination or path
    if not check and (changed or destination is not None):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            "\n".join(converted_lines) + "\n",
            encoding="utf-8",
        )
    return changed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true", help="fail if a dataset still needs migration"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="write normalized copies here without changing author source data",
    )
    args = parser.parse_args()
    if args.check and args.output_dir:
        parser.error("--check and --output-dir cannot be used together")

    changed_files = []
    exported_files = []
    for npc_id, filename in DATASET_FILENAMES.items():
        path = DATA_DIR / filename
        destination = (
            args.output_dir / filename
            if args.output_dir
            else None
        )
        if migrate_file(
            path,
            npc_id,
            check=args.check,
            destination=destination,
        ):
            changed_files.append(path)
        if destination is not None:
            exported_files.append(destination)
    if args.check and changed_files:
        print("Training data needs migration:")
        for path in changed_files:
            print(path.relative_to(ROOT_DIR))
        return 1
    if exported_files:
        print("Exported normalized training data:")
        for path in exported_files:
            print(path)
        return 0
    if changed_files:
        print("Migrated:")
        for path in changed_files:
            print(path.relative_to(ROOT_DIR))
    else:
        print("Training data already uses ModelStoryOutput.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
