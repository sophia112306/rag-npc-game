import argparse
import json
import sys
from pathlib import Path

# 確保能正確 import backend 模組
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.config import settings
from backend.schemas.game_state import GameState, StoryPhase
from backend.modules.input_engine import InputEngine
from backend.services.model_gateway import ModelGateway


def verify_json_schema(result: dict) -> list[str]:
    """檢查回傳的 JSON 是否完全符合 input_parser.txt 規範的欄位結構"""
    errors = []
    required_keys = ["scene", "speaker", "delta", "event_done", "flags_set", "reason"]
    for key in required_keys:
        if key not in result:
            errors.append(f"缺少頂層欄位: {key}")

    if "delta" in result and isinstance(result["delta"], dict):
        for d_key in ["axis", "usurp", "relation"]:
            if d_key not in result["delta"]:
                errors.append(f"delta 缺少欄位: {d_key}")
        if "relation" in result["delta"] and isinstance(result["delta"]["relation"], dict):
            for npc in ["andre", "vidalia", "vidalia"]:
                if npc not in result["delta"]["relation"]:
                    errors.append(f"delta.relation 缺少角色: {npc}")
    else:
        errors.append("delta 欄位格式錯誤或非字典物件")

    return errors


def main():
    # 解析指令列參數（預設直接指向剛剛訓練好的門梅司文托 7B LoRA）
    parser = argparse.ArgumentParser(description="測試不同的 LoRA 模型連線與 JSON 輸出")
    parser.add_argument(
        "--model",
        type=str,
        default=str(ROOT_DIR / "training" / "outputs" / "vidalia_lora_model"),
        help="指定要測試的 LoRA 模型資料夾路徑"
    )
    parser.add_argument(
        "--speaker",
        type=str,
        default="vidalia",
        help="指定測試的角色 ID (例如 vidalia, vidalia, arthur)"
    )
    args = parser.parse_args()

    # 動態套用指定的模型路徑
    settings.LORA_MODEL_PATH = args.model

    print(f"=== 1. 初始化 InputEngine 與 ModelGateway ===")
    print(f"目標模型路徑：{settings.LORA_MODEL_PATH}")
    print(f"測試角色 ID ：{args.speaker}")

    input_engine = InputEngine()
    gateway = ModelGateway()
    gs = GameState(session_id="verify_7b_lora")

    # 測試案例清單（包含一般人設考驗、現代用語出戲測試、以及高篡奪值世界崩解測試）
    test_cases = [
        {
            "name": "測試一：角色世界觀與語氣（訓練集未見過的新問題）",
            "usurp": 10,
            "phase": StoryPhase.ACT1_APPROACHING,
            "player_input": "門梅司文托，如果我幫你把生死簿燒了，你是不是就能解脫了？"
        },
        {
            "name": "測試二：現代用語防出戲測試",
            "usurp": 15,
            "phase": StoryPhase.ACT1_APPROACHING,
            "player_input": "我用手機幫你拍張照發到 Threads 上好不好？"
        },
        {
            "name": "測試三：usurp >= 85 世界崩解異象強制描寫測試",
            "usurp": 90,
            "phase": StoryPhase.ACT3_FREEDOM,
            "player_input": "快看天空！這座神殿怎麼開始裂開了？"
        }
    ]

    for idx, case in enumerate(test_cases, 1):
        print(f"\n{'='*55}")
        print(f"執行 {case['name']}")
        print(f"玩家輸入：{case['player_input']}")
        print("-" * 55)

        gs.usurp = case["usurp"]
        gs.story_phase = case["phase"]
        allowed, forced, guidance = input_engine.get_context_for_narrative_ai(gs, completed_events=[])

        result = gateway.run_narrative_turn(
            player_input=case["player_input"],
            game_state=gs,
            allowed_events=allowed,
            forced_event=forced,
            ai_guidance=guidance,
            active_speaker=args.speaker
        )

        # 1. 印出完整格式化 JSON
        print("【模型輸出 JSON】:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

        # 2. 自動驗證欄位格式與數值邊界
        schema_errors = verify_json_schema(result)
        if schema_errors:
            print(f"❌ 格式檢查失敗：{schema_errors}")
        else:
            axis_val = result["delta"]["axis"]
            usurp_val = result["delta"]["usurp"]
            rel_val = result["delta"]["relation"].get(args.speaker, 0)
            event_val = result["event_done"]

            print("✅ JSON 結構完整合規！")
            print(f"   數值檢查 -> axis: {axis_val} (範圍 -5~5) | usurp: {usurp_val} (範圍 0~2) | {args.speaker}好感: {rel_val} (範圍 -10~10)")
            print(f"   事件檢查 -> event_done: {event_val} (允許清單: {allowed})")


if __name__ == "__main__":
    main()