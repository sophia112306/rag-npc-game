from typing import Dict, List, Optional, Tuple
from backend.schemas.game_state import GameState


class EventRules:
    """固定事件數值套用表與危險事件脫身檢定 (草案 v3 規格)"""

    # -----------------------------------------------------------------
    # 1. 固定事件效果資料庫 (Event Database)
    # -----------------------------------------------------------------
    EVENT_DATABASE: Dict[str, dict] = {
        # 階段一事件
        "E1-1": {"axis": 0, "usurp": 0, "relation": {}, "flags": {}},
        "E1-2": {"axis": 0, "usurp": 0, "relation": {"andre": 5}, "flags": {}},
        "E1-3": {"axis": 0, "usurp": 0, "relation": {"vidalia": 5}, "flags": {}},
        "E1-4": {"axis": 0, "usurp": 0, "relation": {}, "flags": {}},
        "E1-5": {"axis": 0, "usurp": 0, "relation": {"menmesvento": 5}, "flags": {}},

        # 階段二事件
        "E2-1_prevent": {"axis": 0, "usurp": -5, "relation": {"andre": 10}, "flags": {}},
        "E2-1_assist": {"axis": 0, "usurp": 10, "relation": {}, "flags": {"elder_cooperation": True}},
        "E2-1_ignore": {"axis": 0, "usurp": 5, "relation": {}, "flags": {}},

        "E2-2_testify": {"axis": 0, "usurp": 0, "relation": {"menmesvento": 10}, "flags": {"e2_2_testified": True}},

        "E2-3_help_both": {"axis": 0, "usurp": 0, "relation": {}, "flags": {"fissure_map": True, "library_path": True}},
        "E2-3_report": {"axis": -10, "usurp": 5, "relation": {}, "flags": {"elder_cooperation": True}},
        "E2-3_ignore": {"axis": 0, "usurp": 0, "relation": {}, "flags": {}},

        "E2-4_place": {"axis": 0, "usurp": 15, "relation": {}, "flags": {}},
        "E2-4_refuse": {"axis": 0, "usurp": 0, "relation": {}, "flags": {}},
        "E2-4_remove": {"axis": 0, "usurp": -10, "relation": {}, "flags": {}},  # [新增] 拆除符印 (每處 -10)

        # 真相事件
        "Truth_A": {"axis": 0, "usurp": 0, "relation": {}, "flags": {"truth_a_unlocked": True}, "truth_delta": 1},
        "Truth_B": {"axis": 0, "usurp": 0, "relation": {}, "flags": {"truth_b_unlocked": True}, "truth_delta": 1},
        "Truth_C": {"axis": 0, "usurp": 0, "relation": {}, "flags": {"truth_c_unlocked": True}, "truth_delta": 1},  # [修正] 移除寫反的 {-10: "alan"}
        "Truth_C_reject_alan": {"axis": 0, "usurp": -10, "relation": {}, "flags": {"rejected_alan": True}},  # [新增] 真相C後明確拒絕艾倫

        # 警告事件 W
        "W": {"axis": 0, "usurp": 0, "relation": {}, "flags": {"warning_triggered": True, "warning_event_done": True}},
        "W_expose_elders": {"axis": 0, "usurp": -10, "relation": {}, "flags": {"warning_triggered": True, "warning_event_done": True}},

        # 階段三事件
        "E3-1_accept": {"axis": 0, "usurp": 20, "relation": {}, "flags": {"elder_cooperation": True}},
        "E3-2_agree": {"axis": 10, "usurp": 0, "relation": {"menmesvento": 10}, "flags": {}},
        "E3-2_receive_dust_token": {"axis": 0, "usurp": 0, "relation": {"menmesvento": 10}, "flags": {"has_dust_token": True}},
        "E3-3_accept_transformation": {"axis": -20, "usurp": 0, "relation": {"vidalia": 10}, "flags": {"is_transformed": True}},
        "E3-4": {"axis": 0, "usurp": 0, "relation": {"andre": 10}, "flags": {"hidden_cave_unlocked": True}},

        # 終局維塔三問；數值只由固定選項套用，不交給模型自行推測。
        "VETA_Q1_EACH_LIFE": {"axis": 10, "usurp": 0, "relation": {"menmesvento": 20}, "flags": {}},
        "VETA_Q1_RECURRING": {"axis": -10, "usurp": 0, "relation": {"vidalia": 10}, "flags": {}},
        "VETA_Q2_REMEMBER": {"axis": 10, "usurp": 0, "relation": {"menmesvento": 10}, "flags": {}},
        "VETA_Q2_RELEASE": {"axis": -10, "usurp": 0, "relation": {"vidalia": 30}, "flags": {}},
        "VETA_Q2_CONTROL": {"axis": 0, "usurp": 90, "relation": {}, "flags": {}},
        "VETA_USURP_CONFIRM": {"axis": 0, "usurp": 15, "relation": {}, "flags": {}, "clear_warning_cooldown": True},
    }

    @staticmethod
    def get_event_effect(event_id: str) -> Optional[dict]:
        """取得指定事件的數值增減與旗標變更"""
        return EventRules.EVENT_DATABASE.get(event_id)

    # -----------------------------------------------------------------
    # 2. 危險事件 (E2-2, E3-1) 脫身檢定邏輯
    # -----------------------------------------------------------------
    @staticmethod
    def evaluate_danger_event(
        game_state: GameState,
        event_id: str,
        player_action_args: dict
    ) -> Tuple[bool, str]:
        """
        判定玩家在危險事件中是否脫身成功。
        """
        # (1) E2-2 百年審判危險判定
        if event_id == "E2-2":
            has_name = player_action_args.get("called_soul_name", False)
            has_map = game_state.flags.get("fissure_map", False)
            andre_rel = game_state.npc_states.get("andre").relation if "andre" in game_state.npc_states else 0
            andre_help = andre_rel >= 40

            if has_name or has_map or andre_help:
                return True, "成功脫身：通過審判考驗或獲得援助。"
            else:
                return False, "脫身失敗：木乃伊碎裂為裂沙者攻擊主角，主角死亡並觸發轉化程序。"

        # (2) E3-1 長老會的提議 (灰燼之根追殺)
        elif event_id == "E3-1":
            andre_rel = game_state.npc_states.get("andre").relation if "andre" in game_state.npc_states else 0
            vidalia_rel = game_state.npc_states.get("vidalia").relation if "vidalia" in game_state.npc_states else 0
            has_map = game_state.flags.get("fissure_map", False)

            if andre_rel >= 40 or has_map or vidalia_rel >= 60:
                return True, "成功脫身：借助陣營庇護或地理優勢甩開灰燼之根追殺。"
            else:
                return False, "脫身失敗：遭灰燼之根部隊包圍，主角死亡並觸發轉化程序。"

        return True, "非危險事件，預設安全。"

    # -----------------------------------------------------------------
    # 3. [新增] 門梅司文托閉門不見與安德烈引薦恢復邏輯
    # -----------------------------------------------------------------
    @staticmethod
    def check_menmesvento_recovery(game_state: GameState) -> Tuple[bool, str]:
        """
        規則：門梅司文托 < 10 會閉門不見；若安德烈 >= 60 引薦，可恢復至 20。
        """
        if "menmesvento" not in game_state.npc_states or "andre" not in game_state.npc_states:
            return False, ""

        men_npc = game_state.npc_states["menmesvento"]
        andre_rel = game_state.npc_states["andre"].relation

        if men_npc.relation < 10 and andre_rel >= 60:
            men_npc.relation = 20
            return True, "安德烈出面引薦，門梅司文托重新敞開大門（關係值恢復至 20）。"

        return False, ""
