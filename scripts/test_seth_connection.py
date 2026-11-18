import argparse
import glob
import json
from pathlib import Path
from unsloth import FastLanguageModel

ROOT_DIR = Path(__file__).resolve().parent.parent


def verify_output(result) -> list[str]:
    """檢查回傳結果是否合規（支援純台詞字串或 JSON 字典）"""
    errors = []

    # 情況 A：純台詞字串
    if isinstance(result, str):
        if not result.strip():
            errors.append("回傳台詞為空字串")
        if result.strip().startswith("{") and result.strip().endswith("}"):
            errors.append("警告：塞特應該輸出純台詞，但偵測到 JSON 括號結構")
        return errors

    # 情況 B：JSON 字典（若訓練集是 JSON 格式）
    if isinstance(result, dict):
        if "line" in result:
            if not str(result["line"]).strip():
                errors.append("JSON 中的 line 為空字串")
        else:
            errors.append("JSON 缺少 line 欄位")
        return errors

    errors.append(f"未預期的回傳型別: {type(result)}")
    return errors


def load_system_prompt(speaker: str) -> str:
    """從訓練集自動讀取對應角色的 System Prompt"""
    files = (
        glob.glob(str(ROOT_DIR / f"training/**/*{speaker}*.jsonl"), recursive=True)
        or glob.glob(str(ROOT_DIR / "training/**/*塞特*.jsonl"), recursive=True)
    )
    if not files:
        raise FileNotFoundError(f"在 training/ 下找不到 {speaker} 的 .jsonl 訓練集！")

    print(f"📂 讀取訓練集 System Prompt 來源：{files[0]}")
    with open(files[0], "r", encoding="utf-8") as f:
        first_data = json.loads(f.readline())
        return next((m["content"] for m in first_data["messages"] if m["role"] == "system"), "")


def main():
    parser = argparse.ArgumentParser(description="測試塞特 LoRA 模型輸出與人設格式")
    parser.add_argument(
        "--model",
        type=str,
        default=str(ROOT_DIR / "training" / "outputs" / "seth_lora_model"),
        help="指定要測試的 LoRA 模型資料夾路徑"
    )
    parser.add_argument(
        "--speaker",
        type=str,
        default="seth",
        help="指定測試的角色 ID (預設 seth)"
    )
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

    # 塞特專屬測試案例清單（弱氣膽小人設語氣、現代用語防出戲、高篡奪值情境）
    test_cases = [
        {
            "name": "測試一：塞特人設語氣與背景考驗（訓練集未見過的新問題）",
            "scene_context": "【當前狀態】場景：礦區搬運點 | 階段：第一幕（接近中） | 篡奪值(usurp)：10",
            "player_input": "塞特，你每天在這裡搬重物不會覺得很辛苦嗎？為什麼不試著離開這裡？"
        },
        {
            "name": "測試二：現代用語防出戲測試",
            "scene_context": "【當前狀態】場景：礦區搬運點 | 階段：第一幕（接近中） | 篡奪值(usurp)：15",
            "player_input": "我用手機幫你拍張照發到 Threads 上好不好？"
        },
        {
            "name": "測試三：usurp >= 85 高壓異象情境測試",
            "scene_context": "【當前狀態】場景：聖火反應爐核心區（空間裂縫擴大中） | 階段：第三幕（高壓異象） | 篡奪值(usurp)：90",
            "player_input": "快看周圍！空間的裂縫正在擴大，聖火反應爐也快失控了，我們該怎麼辦？"
        }
    ]

    for idx, case in enumerate(test_cases, 1):
        print(f"\n{'='*55}")
        print(f"執行 {case['name']}")
        print(f"情境條件：{case['scene_context']}")
        print(f"玩家輸入：{case['player_input']}")
        print("-" * 55)

        full_system_prompt = f"{base_system_prompt}\n{case['scene_context']}"
        messages = [
            {"role": "system", "content": full_system_prompt},
            {"role": "user", "content": case["player_input"]}
        ]

        inputs = tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt"
        ).to("cuda")

        outputs = model.generate(
            input_ids=inputs,
            max_new_tokens=512,
            temperature=0.7
        )
        raw_reply = tokenizer.decode(outputs[0][inputs.shape[-1]:], skip_special_tokens=True).strip()

        # 嘗試判斷是 JSON 還是純台詞
        parsed_result = raw_reply
        if raw_reply.startswith("{") and raw_reply.endswith("}"):
            try:
                parsed_result = json.loads(raw_reply)
            except json.JSONDecodeError:
                pass

        # 1. 印出模型輸出結果
        if isinstance(parsed_result, dict):
            print("【模型輸出 JSON】:")
            print(json.dumps(parsed_result, ensure_ascii=False, indent=2))
        else:
            print("【模型輸出純台詞】:")
            print(parsed_result)

        # 2. 自動驗證輸出格式
        errors = verify_output(parsed_result)
        if errors:
            print(f"❌ 檢查失敗：{errors}")
        else:
            print("✅ 輸出格式檢查通過！")


if __name__ == "__main__":
    main()