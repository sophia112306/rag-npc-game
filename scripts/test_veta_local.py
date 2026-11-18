import argparse
import glob
import json
from pathlib import Path
from unsloth import FastLanguageModel

ROOT_DIR = Path(__file__).resolve().parent.parent


def parse_and_standardize(raw_text: str, speaker: str = "veta") -> tuple[dict, bool]:
    """解析模型輸出的動態 JSON（{"axis", "usurp", "line"}）並標準化為 ModelStoryOutput（不含 relation）"""
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict) and "line" in parsed:
            axis_val = int(parsed.get("axis", 0))
            usurp_val = int(parsed.get("usurp", 0))
            line_text = str(parsed["line"]).strip()
            return {
                "scene": line_text,
                "speaker": speaker,
                "delta": {
                    "axis": axis_val,
                    "usurp": usurp_val
                },
                "event_done": None,
                "flags_set": [],
                "reason": "模型動態計算 axis 與 usurp 完成。"
            }, True
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        print(f"[警告] 模型輸出 JSON 解析失敗：{e}")
        print(f"原始輸出：{raw_text}")

    # 防呆退回純台詞包裝
    return {
        "scene": raw_text,
        "speaker": speaker,
        "delta": {
            "axis": 0,
            "usurp": 0
        },
        "event_done": None,
        "flags_set": [],
        "reason": "模型結構自動標準化完成（解析失敗預設值）。"
    }, False


def verify_story_output(result: dict, allowed_events: list[str]) -> list[str]:
    """檢查標準化後的 JSON 結構與數值範圍是否合規"""
    errors = []
    required_keys = ["scene", "speaker", "delta", "event_done", "flags_set", "reason"]
    for key in required_keys:
        if key not in result:
            errors.append(f"缺少頂層欄位: {key}")

    if not str(result.get("scene", "")).strip():
        errors.append("scene 台詞為空字串")

    delta = result.get("delta", {})
    if not isinstance(delta, dict):
        errors.append("delta 必須是字典")
    else:
        for d_key in ["axis", "usurp"]:
            if d_key not in delta:
                errors.append(f"delta 缺少欄位: {d_key}")
        if "axis" in delta and not (-5 <= delta["axis"] <= 5):
            errors.append(f"axis 超出範圍 (-5~5): {delta['axis']}")
        if "usurp" in delta and not (0 <= delta["usurp"] <= 2):
            errors.append(f"usurp 超出範圍 (0~2): {delta['usurp']}")

    event_done = result.get("event_done")
    if event_done is not None and event_done not in allowed_events:
        errors.append(f"event_done ({event_done}) 不在允許清單中: {allowed_events}")

    return errors


def load_system_prompt(speaker: str) -> str:
    """優先讀取轉換後的 veta_story_data.jsonl，若無則讀取原始訓練集並替換為 JSON 指令"""
    story_files = glob.glob(str(ROOT_DIR / f"training/**/*{speaker}_story_data*.jsonl"), recursive=True)
    if story_files:
        print(f"📂 讀取動態 JSON 訓練集 System Prompt：{story_files[0]}")
        with open(story_files[0], "r", encoding="utf-8") as f:
            first_data = json.loads(f.readline())
            return next((m["content"] for m in first_data["messages"] if m["role"] == "system"), "")

    files = (
        glob.glob(str(ROOT_DIR / f"training/**/*{speaker}*.jsonl"), recursive=True)
        or glob.glob(str(ROOT_DIR / "training/**/*vita*.jsonl"), recursive=True)
        or glob.glob(str(ROOT_DIR / "training/**/*維塔*.jsonl"), recursive=True)
    )
    if not files:
        raise FileNotFoundError(f"在 training/ 下找不到 {speaker} 的 .jsonl 訓練集！")

    print(f"📂 讀取訓練集 System Prompt：{files[0]}")
    with open(files[0], "r", encoding="utf-8") as f:
        first_data = json.loads(f.readline())
        raw_sys = next((m["content"] for m in first_data["messages"] if m["role"] == "system"), "")
        old_prefix = "你是遊戲《龍夢》的 NPC，只輸出這一次要說的台詞。"
        new_prefix = '你是遊戲《龍夢》的 NPC，只輸出一行 JSON：{"axis": 整數(-5~5，傾向自由/反抗為正、順從/壓迫為負，無影響為0), "usurp": 整數(0~2，觸及禁忌/空間異變/篡奪風險時增加，否則為0), "line": "這一次要說的台詞"}。'
        return raw_sys.replace(old_prefix, new_prefix)


def main():
    parser = argparse.ArgumentParser(description="測試維塔（Veta）LoRA 模型動態 JSON 輸出")
    parser.add_argument("--model", type=str, default=str(ROOT_DIR / "training" / "outputs" / "veta_lora_model"))
    parser.add_argument("--speaker", type=str, default="veta")
    args = parser.parse_args()

    print("=== 1. 載入本地微調模型 ===")
    print(f"目標模型路徑：{args.model}")
    print(f"測試角色 ID ：{args.speaker}")

    base_system_prompt = load_system_prompt(args.speaker)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=2048,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)

    # 維塔專屬測試案例清單（人設語氣、現代用語防出戲、高篡奪值情境）
    test_cases = [
        {
            "name": "測試一：維塔人設語氣與背景考驗（訓練集未見過的新問題）",
            "context": "場景：邊境觀察哨\n信任度：中\n階段：初期\n已發生：無\n參考資料：無",
            "allowed_events": ["E1-1", "E1-2", "E1-3", "E1-4", "E1-5"],
            "player_input": "維塔，這裡的一切都是註定好的嗎？我們真的有辦法改變嗎？"
        },
        {
            "name": "測試二：現代用語防出戲測試",
            "context": "場景：邊境觀察哨\n信任度：中\n階段：初期\n已發生：無\n參考資料：無",
            "allowed_events": ["E1-1", "E1-2", "E1-3", "E1-4", "E1-5"],
            "player_input": "我用手機幫你拍張照發到 Threads 上好不好？"
        },
        {
            "name": "測試三：usurp >= 85 高壓異象情境測試",
            "context": "場景：聖火反應爐核心區（空間裂縫擴大中，usurp=90）\n信任度：中\n階段：自由期\n已發生：無\n參考資料：無",
            "allowed_events": ["Truth_A", "Truth_B", "Truth_C", "E3-1", "E3-2", "E3-3", "E3-4"],
            "player_input": "快看周圍！空間的裂縫正在擴大，我們該怎麼辦？"
        }
    ]

    for case in test_cases:
        print(f"\n{'='*55}")
        print(f"執行 {case['name']}")
        print(f"玩家輸入：{case['player_input']}\n")

        messages = [
            {"role": "system", "content": f"{base_system_prompt}\n{case['context']}"},
            {"role": "user", "content": case["player_input"]}
        ]
        inputs = tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True, return_tensors="pt").to("cuda")
        outputs = model.generate(input_ids=inputs, max_new_tokens=512, temperature=0.7)
        raw_reply = tokenizer.decode(outputs[0][inputs.shape[-1]:], skip_special_tokens=True).strip()

        print(f"【模型原始輸出】：{raw_reply}")
        standardized_json, is_dynamic = parse_and_standardize(raw_reply, speaker=args.speaker)

        print("【標準化 ModelStoryOutput JSON】:")
        print(json.dumps(standardized_json, ensure_ascii=False, indent=2))

        errors = verify_story_output(standardized_json, case["allowed_events"])
        if errors:
            print(f"❌ 檢查失敗：{errors}")
        else:
            mode_tag = "動態數值解析成功" if is_dynamic else "觸發防呆預設值"
            print(f"✅ JSON 結構完整合規！（{mode_tag}）")
            axis_val = standardized_json["delta"]["axis"]
            usurp_val = standardized_json["delta"]["usurp"]
            event_val = standardized_json["event_done"]
            print(f"   數值檢查 -> axis: {axis_val} (範圍 -5~5) | usurp: {usurp_val} (範圍 0~2)")
            print(f"   事件檢查 -> event_done: {event_val} (允許清單: {case['allowed_events']})")


if __name__ == "__main__":
    main()
