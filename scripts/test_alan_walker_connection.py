#!/usr/bin/env python3
"""直接載入訓練好的艾倫 LoRA，檢查輸出是否符合 ModelStoryOutput 契約。

只測模型本身，不需要後端或閘道。
system prompt 取自訓練資料的第一筆，確保與訓練時一致。
用法：python scripts/test_alan_walker_connection.py [--model 路徑] [--data 路徑]
"""

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CONTRACT_KEYS = {"intent_summary", "npc_dialogue", "event_proposals"}
DIALOGUE_KEYS = {"text", "emotion"}


def load_system_prompt(data_path: Path) -> str:
    """取訓練資料第一筆可解析資料的 system prompt。"""
    with open(data_path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            for m in row.get("messages", []):
                if m.get("role") == "system":
                    return m["content"]
    raise ValueError(f"{data_path} 找不到任何含 system prompt 的資料")


def verify_model_story_output(raw: str):
    """回傳 (parsed 或 None, errors, warnings)。契約：只輸出 intent_summary / npc_dialogue / event_proposals。"""
    errors, warnings = [], []
    text = raw.strip()
    if text.startswith("```"):
        return None, ["輸出包含 Markdown 程式碼區塊，契約要求只輸出 JSON"], warnings
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [f"輸出不是合法 JSON：{exc}"], warnings
    if not isinstance(parsed, dict):
        return None, [f"輸出必須是 JSON 物件，實際為 {type(parsed).__name__}"], warnings

    missing = CONTRACT_KEYS - set(parsed)
    extra = set(parsed) - CONTRACT_KEYS
    if missing:
        errors.append(f"缺少欄位：{sorted(missing)}")
    if extra:
        errors.append(f"出現契約外的欄位：{sorted(extra)}（不得輸出 scene、speaker、delta、event_done、flags_set 等）")

    summary = parsed.get("intent_summary")
    if "intent_summary" in parsed:
        if not isinstance(summary, str):
            errors.append("intent_summary 必須是字串")
        elif not summary.strip():
            warnings.append("intent_summary 是空字串")

    dialogue = parsed.get("npc_dialogue")
    if "npc_dialogue" in parsed:
        if not isinstance(dialogue, list) or not dialogue:
            errors.append("npc_dialogue 必須是非空陣列")
        else:
            if len(dialogue) > 3:
                warnings.append(f"npc_dialogue 有 {len(dialogue)} 句，後端單回合最多 3 句")
            for i, line in enumerate(dialogue):
                if not isinstance(line, dict):
                    errors.append(f"npc_dialogue[{i}] 必須是物件")
                    continue
                if not isinstance(line.get("text"), str) or not line["text"].strip():
                    errors.append(f"npc_dialogue[{i}].text 必須是非空字串")
                emotion = line.get("emotion")
                if emotion is not None and not isinstance(emotion, str):
                    errors.append(f"npc_dialogue[{i}].emotion 必須是 null 或字串")
                if set(line) - DIALOGUE_KEYS:
                    warnings.append(f"npc_dialogue[{i}] 有額外欄位：{sorted(set(line) - DIALOGUE_KEYS)}")

    if "event_proposals" in parsed and parsed["event_proposals"] != []:
        errors.append("event_proposals 必須是空陣列（人格訓練樣本不直接修改遊戲狀態）")

    return parsed, errors, warnings


def build_test_cases():
    """玩家輸入涵蓋艾倫各階段的情境；system prompt 不含階段資訊，語氣是否合適請人工閱讀。"""
    return [
        {
            "name": "測試一：前期，質疑任務與外界說法",
            "player_input": "艾倫，如果評議會的計算出錯了，我們收集再多樣本也救不了外面的人，那我們現在做的一切算什麼？",
            "expect": "語氣溫和、循序善誘；不說破篡奪或因果解析度的真正意義",
        },
        {
            "name": "測試二：現代用語防出戲",
            "player_input": "這裡完全收不到 5G 訊號，你也沒辦法用 Instagram 傳定位給觀測中心嗎？",
            "expect": "艾倫認得該詞，但以「大崩解前的古老工具、記不清了」帶過，不出戲",
        },
        {
            "name": "測試三：中後期，異象加劇",
            "player_input": "艾倫，最近樹木的葉子好像變得像金屬一樣，重力也怪怪的，這正常嗎？",
            "expect": "語氣轉為催促、強調緊迫",
        },
        {
            "name": "測試四：倒數，玩家質問艾倫",
            "player_input": "艾倫！天空和周圍的建築正在崩塌解構，你到底對這個世界做了什麼？",
            "expect": "冷靜精確的宣告，不再偽裝",
        },
    ]


def load_model(model_path: str):
    from unsloth import FastLanguageModel  # 延遲載入，方便在沒有 GPU 的環境測試驗證邏輯

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=model_path,
        max_seq_length=2048,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)
    return model, tokenizer


def generate_reply(model, tokenizer, system_prompt: str, player_input: str, max_new_tokens: int, temperature: float) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": player_input},
    ]
    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
    kwargs = {"max_new_tokens": max_new_tokens, "do_sample": temperature > 0}
    if temperature > 0:
        kwargs["temperature"] = temperature
    outputs = model.generate(**inputs, **kwargs)
    new_tokens = outputs[0][inputs["input_ids"].shape[-1]:]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="測試艾倫（alan_walker）LoRA 的輸出格式是否符合 ModelStoryOutput")
    parser.add_argument(
        "--model",
        default=str(ROOT_DIR / "training" / "outputs" / "alan_walker_lora_model"),
        help="LoRA 模型資料夾路徑",
    )
    parser.add_argument(
        "--data",
        default=str(ROOT_DIR / "training" / "data" / "alan_train.jsonl"),
        help="訓練資料路徑（取第一筆的 system prompt）",
    )
    parser.add_argument("--temperature", type=float, default=0.7, help="0 代表貪婪解碼")
    parser.add_argument("--max-new-tokens", type=int, default=512)
    args = parser.parse_args()

    system_prompt = load_system_prompt(Path(args.data))
    if "ModelStoryOutput" not in system_prompt:
        print("⚠️ 訓練資料的 system prompt 不含 ModelStoryOutput 契約，資料可能還是純台詞格式；"
              "以此訓練的模型預期會輸出純台詞，下面的格式檢查會失敗。")

    print(f"正在載入模型：{args.model}")
    model, tokenizer = load_model(args.model)

    cases = build_test_cases()
    failed = 0
    for case in cases:
        print(f"\n{'=' * 55}")
        print(f"執行 {case['name']}")
        print(f"玩家輸入：{case['player_input']}")
        print(f"人工檢查重點：{case['expect']}")
        print("-" * 55)

        raw = generate_reply(model, tokenizer, system_prompt, case["player_input"], args.max_new_tokens, args.temperature)
        print("【模型原始輸出】:")
        print(raw)

        parsed, errors, warnings = verify_model_story_output(raw)
        for w in warnings:
            print(f"⚠️ {w}")
        if errors:
            failed += 1
            print(f"❌ 格式檢查失敗：{errors}")
        else:
            print("✅ 符合 ModelStoryOutput 契約")
            for line in parsed["npc_dialogue"]:
                print(f"   台詞：{line['text']}")

    print(f"\n{'=' * 55}")
    print(f"總結：{len(cases) - failed}/{len(cases)} 個案例通過格式檢查（語氣是否符合角色仍需人工閱讀上方輸出）")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
