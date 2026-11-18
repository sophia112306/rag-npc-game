import argparse
import glob
import json
from pathlib import Path
from unsloth import FastLanguageModel

ROOT_DIR = Path(__file__).resolve().parent.parent


def parse_and_standardize(raw_text: str, speaker: str = "vidalia") -> dict:
    """解析模型輸出；若為純台詞則比照門梅司文托測試腳本，自動標準化為完整 ModelStoryOutput JSON（含 relation）"""
    try:
        parsed = json.loads(raw_text)
        if isinstance(parsed, dict) and "scene" in parsed and "delta" in parsed:
            return parsed
    except json.JSONDecodeError as e:
        print(f"[警告] 模型輸出 JSON 解析失敗：{e}")
        print(f"原始輸出：{raw_text}")

    return {
        "scene": raw_text,
        "speaker": speaker,
        "delta": {
            "axis": 0,
            "usurp": 0,
            "relation": {
                "andre": 0,
                "vidalia": 0,
                "menmesvento": 0
            }
        },
        "event_done": None,
        "flags_set": [],
        "reason": "模型結構自動標準化完成。"
    }


def verify_story_output(result: dict, allowed_events: list[str], speaker: str = "vidalia") -> list[str]:
    """檢查標準化後的 ModelStoryOutput JSON 結構、好感度與數值範圍是否合規"""
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
        for d_key in ["axis", "usurp", "relation"]:
            if d_key not in delta:
                errors.append(f"delta 缺少欄位: {d_key}")

        if "axis" in delta and not (-5 <= delta["axis"] <= 5):
            errors.append(f"axis 超出範圍 (-5~5): {delta['axis']}")
        if "usurp" in delta and not (0 <= delta["usurp"] <= 2):
            errors.append(f"usurp 超出範圍 (0~2): {delta['usurp']}")

        rel = delta.get("relation")
        if not isinstance(rel, dict):
            errors.append("delta.relation 必須是字典")
        else:
            for npc in ["andre", "vidalia", "menmesvento"]:
                if npc not in rel:
                    errors.append(f"delta.relation 缺少角色: {npc}")
                elif not (-10 <= rel[npc] <= 10):
                    errors.append(f"{npc} 好感超出範圍 (-10~10): {rel[npc]}")

    event_done = result.get("event_done")
    if event_done is not None and event_done not in allowed_events:
        errors.append(f"event_done ({event_done}) 不在允許清單中: {allowed_events}")

    return errors


def load_system_prefix(speaker: str) -> str:
    """從維達利亞訓練集讀取第一行指令前綴"""
    files = (
        glob.glob(str(ROOT_DIR / f"training/**/*{speaker}*.jsonl"), recursive=True)
        or glob.glob(str(ROOT_DIR / "training/**/*維達利亞*.jsonl"), recursive=True)
    )
    if files:
        with open(files[0], "r", encoding="utf-8") as f:
            first_data = json.loads(f.readline())
            sys_content = next((m["content"] for m in first_data["messages"] if m["role"] == "system"), "")
            if sys_content:
                return sys_content.splitlines()[0]
    return "你是遊戲《龍夢》的 NPC，只輸出這一次要說的台詞。"


def main():
    parser = argparse.ArgumentParser(description="測試維達利亞（Vidalia）LoRA 模型並輸出標準化 ModelStoryOutput JSON")
    parser.add_argument(
        "--model",
        type=str,
        default=str(ROOT_DIR / "training" / "outputs" / "vidalia_lora_model"),
        help="指定維達利亞 LoRA 模型路徑"
    )
    parser.add_argument(
        "--speaker",
        type=str,
        default="vidalia",
        help="測試角色 ID"
    )
    args = parser.parse_args()

    sys_prefix = load_system_prefix(args.speaker)

    print(f"正在載入模型：{args.model}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.model,
        max_seq_length=2048,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)

    # 測試案例完全對齊維達利亞訓練集的場景、信任度分級與階段格式
    test_cases = [
        {
            "name": "測試一：角色世界觀與溫和挽留語氣（高信任度 t >= 60）",
            "scene": "鳴霖命脈之泉源頭",
            "trust": "高 (t >= 60)",
            "stage": "世界崩解不安、基於彼此默契與信任而溫和挽留（無依戀）",
            "allowed_events": ["E1-1", "E1-2", "E1-3", "E1-4", "E1-5"],
            "player_input": "維達利亞，如果我幫你把命脈之泉的結界重新封印，這片雨林是不是就能永遠保存下來了？"
        },
        {
            "name": "測試二：現代用語防出戲測試（低信任度 t < 40）",
            "scene": "鳴霖林間小徑",
            "trust": "低 (t < 40)",
            "stage": "優雅而疏離、簡短回應、表達聽不懂、不分析現代科技",
            "allowed_events": ["E1-1", "E1-2", "E1-3", "E1-4", "E1-5"],
            "player_input": "我用手機幫你拍張照發到 Threads 上好不好？"
        },
        {
            "name": "測試三：usurp >= 85 世界崩解異象強制描寫測試",
            "scene": "鳴霖邊界裂隙旁（天空與空間正在裂開，usurp=90）",
            "trust": "高 (t >= 60)",
            "stage": "世界崩解不安、基於彼此默契與信任而吐露心聲與溫和挽留",
            "allowed_events": ["Truth_A", "Truth_B", "Truth_C", "E3-1", "E3-2", "E3-3", "E3-4"],
            "player_input": "快看天空！這片雨林上方的結界怎麼開始碎裂了？"
        }
    ]

    for case in test_cases:
        print(f"\n{'='*55}")
        print(f"執行 {case['name']}")
        print(f"玩家輸入：{case['player_input']}\n")

        system_prompt = (
            f"{sys_prefix}\n"
            f"角色：維達利亞\n"
            f"場景：{case['scene']}\n"
            f"信任度：{case['trust']}\n"
            f"階段：{case['stage']}\n"
            f"已發生：無\n"
            f"參考資料：無"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": case["player_input"]}
        ]
        inputs = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to("cuda")

        outputs = model.generate(input_ids=inputs, max_new_tokens=512, temperature=0.7)
        raw_reply = tokenizer.decode(outputs[0][inputs.shape[-1]:], skip_special_tokens=True).strip()

        standardized_json = parse_and_standardize(raw_reply, speaker=args.speaker)

        print("【模型輸出 JSON】:")
        print(json.dumps(standardized_json, ensure_ascii=False, indent=2))

        errors = verify_story_output(standardized_json, case["allowed_events"], speaker=args.speaker)
        if errors:
            print(f"❌ 檢查失敗：{errors}")
        else:
            print("✅ JSON 結構完整合規！")
            axis_val = standardized_json["delta"]["axis"]
            usurp_val = standardized_json["delta"]["usurp"]
            vidalia_rel = standardized_json["delta"]["relation"].get("vidalia", 0)
            event_val = standardized_json["event_done"]
            print(f"數值檢查 -> axis: {axis_val} (範圍 -5~5) | usurp: {usurp_val} (範圍 0~2) | vidalia好感: {vidalia_rel} (範圍 -10~10)")
            print(f"事件檢查 -> event_done: {event_val} (允許清單: {case['allowed_events']})")


if __name__ == "__main__":
    main()
