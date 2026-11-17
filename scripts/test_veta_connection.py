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


def verify_output(result) -> list[str]:
    """檢查回傳結果是否合規（支援純台詞字串或後端包裝後的 JSON 字典）"""
    errors = []

    # 情況 A：如果模型/Gateway 直接回傳純台詞字串
    if isinstance(result, str):
        if not result.strip():
            errors.append("回傳台詞為空字串")
        if result.strip().startswith("{") and result.strip().endswith("}"):
            errors.append("警告：維塔應該輸出純台詞，但偵測到 JSON 括號結構")
        return errors

    # 情況 B：如果 ModelGateway 有將純台詞與狀態包裝成字典回傳
    if isinstance(result, dict):
        required_keys = ["scene", "speaker", "delta", "event_done", "flags_set", "reason"]
        for key in required_keys:
            if key not in result:
                errors.append(f"缺少頂層欄位: {key}")

        if "delta" in result and isinstance(result["delta"], dict):
            for d_key in ["axis", "usurp", "relation"]:
                if d_key not in result["delta"]:
                    errors.append(f"delta 缺少欄位: {d_key}")
            if "relation" in result["delta"] and isinstance(result["delta"]["relation"], dict):
                # 檢查常見 NPC 關係欄位（依實際專案角色清單調整）
                for npc in ["andre", "vidalia", "menmesvento"]:
                    if npc not in result["delta"]["relation"]:
                        errors.append(f"delta.relation 缺少角色: {npc}")
        else:
            errors.append("delta 欄位格式錯誤或非字典物件")
        return errors

    errors.append(f"未預期的回傳型別: {type(result)}")
    return errors


def main():
    # 解析指令列參數（預設直接指向剛剛訓練好的維塔 7B LoRA）
    parser = argparse.ArgumentParser(description="測試維塔 LoRA 模型連線與後端整合輸出")
    parser.add_argument(
        "--model",
        type=str,
        default=str(ROOT_DIR / "training" / "outputs" / "veta_lora_model"),
        help="指定要測試的 LoRA 模型資料夾路徑"
    )
    parser.add_argument(
        "--speaker",
        type=str,
        default="veta",
        help="指定測試的角色 ID (例如 veta, menmesvento, vidalia)"
    )
    args = parser.parse_args()

    # 動態套用指定的模型路徑
    settings.LORA_MODEL_PATH = args.model

    print(f"=== 1. 初始化 InputEngine 與 ModelGateway ===")
    print(f"目標模型路徑：{settings.LORA_MODEL_PATH}")
    print(f"測試角色 ID ：{args.speaker}")

    input_engine = InputEngine()
    gateway = ModelGateway()
    gs = GameState(session_id="verify_veta_7b_lora")

    # 維塔專屬測試案例清單（人設語氣、現代用語防出戲、高篡奪值情境）
    test_cases = [
        {
            "name": "測試一：維塔人設語氣與背景考驗（訓練集未見過的新問題）",
            "usurp": 10,
            "phase": StoryPhase.ACT1_APPROACHING,
            "player_input": "維塔，這裡的一切都是註定好的嗎？我們真的有辦法改變嗎？"
        },
        {
            "name": "測試二：現代用語防出戲測試",
            "usurp": 15,
            "phase": StoryPhase.ACT1_APPROACHING,
            "player_input": "我用手機幫你拍張照發到 Threads 上好不好？"
        },
        {
            "name": "測試三：usurp >= 85 高壓異象情境測試",
            "usurp": 90,
            "phase": StoryPhase.ACT3_FREEDOM,
            "player_input": "快看周圍！空間的裂縫正在擴大，我們該怎麼辦？"
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

        # 1. 印出模型/Gateway 輸出結果
        if isinstance(result, dict):
            print("【模型 / Gateway 輸出 JSON】:")
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print("【模型輸出純台詞】:")
            print(result)

        # 2. 自動驗證輸出格式與數值
        errors = verify_output(result)
        if errors:
            print(f"❌ 檢查失敗：{errors}")
        else:
            print("✅ 輸出格式檢查通過！")
            if isinstance(result, dict):
                axis_val = result["delta"]["axis"]
                usurp_val = result["delta"]["usurp"]
                rel_val = result["delta"]["relation"].get(args.speaker, 0)
                event_val = result["event_done"]
                print(f"   數值檢查 -> axis: {axis_val} (範圍 -5~5) | usurp: {usurp_val} (範圍 0~2) | {args.speaker}好感: {rel_val} (範圍 -10~10)")
                print(f"   事件檢查 -> event_done: {event_val} (允許清單: {allowed})")


if __name__ == "__main__":
    main()