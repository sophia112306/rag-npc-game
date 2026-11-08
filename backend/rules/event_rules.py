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

        # 真相事件
        "Truth_A": {"axis": 0, "usurp": 0, "relation": {}, "flags": {"truth_a_unlocked": True}, "truth_delta": 1},
        "Truth_B": {"axis": 0, "usurp": 0, "relation": {}, "flags": {"truth_b_unlocked": True}, "truth_delta": 1},
        "Truth_C": {"axis": 0, "usurp": 0, "relation": {-10: "alan"}, "flags": {"truth_c_unlocked": True}, "truth_delta": 1},

        # 警告事件 W
        "W": {"axis": 0, "usurp": 0, "relation": {}, "flags": {"warning_triggered": True}},
        "W_expose_elders": {"axis": 0, "usurp": -10, "relation": {}, "flags": {}},

        # 階段三事件
        "E3-1_accept": {"axis": 0, "usurp": 20, "relation": {}, "flags": {"elder_cooperation": True}},
        "E3-2_agree": {"axis": 10, "usurp": 0, "relation": {"menmesvento": 10}, "flags": {}},
        "E3-3_accept_transformation": {"axis": -20, "usurp": 0, "relation": {"vidalia": 10}, "flags": {"is_transformed": True}},
        "E3-4": {"axis": 0, "usurp": 0, "relation": {"andre": 10}, "flags": {"hidden_cave_unlocked": True}},
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

        :param game_state: 當前遊戲狀態
        :param event_id: 'E2-2' 或 'E3-1'
        :param player_action_args: 包含玩家選擇的脫身方式參數 (如 choice='call_name', help_npc='andre')
        :return: (是否存活, 原因描述)
        """
        # (1) E2-2 百年審判危險判定
        if event_id == "E2-2":
            # 脫身方式選項：
            # 1. 叫出被唱出的名字 (call_name)
            # 2. 持有裂隙地圖 (has_fissure_map)
            # 3. 安德烈關係值 >= 40 在場援助
            has_name = player_action_args.get("called_soul_name", False)
            has_map = game_state.flags.get("fissure_map", False)
            andre_rel = game_state.npc_states.get("andre").relation if "andre" in game_state.npc_states else 0
            andre_help = andre_rel >= 40

            # 滿足任意一種脫身方式即算成功
            if has_name or has_map or andre_help:
                return True, "成功脫身：通過審判考驗或獲得援助。"
            else:
                return False, "脫身失敗：木乃伊碎裂為裂沙者攻擊主角，主角死亡並觸發轉化程序。"

        # (2) E3-1 長老會的提議 (灰燼之根追殺)
        elif event_id == "E3-1":
            # 脫身方式選項：
            # 1. 安德烈關係值 >= 40 編織隱匿結界
            # 2. 持有裂隙地圖逃入流塵谷
            # 3. 維達利亞關係值 >= 60 躲進鳴霖
            andre_rel = game_state.npc_states.get("andre").relation if "andre" in game_state.npc_states else 0
            vidalia_rel = game_state.npc_states.get("vidalia").relation if "vidalia" in game_state.npc_states else 0
            has_map = game_state.flags.get("fissure_map", False)

            if andre_rel >= 40 or has_map or vidalia_rel >= 60:
                return True, "成功脫身：借助陣營庇護或地理優勢甩開灰燼之根追殺。"
            else:
                return False, "脫身失敗：遭灰燼之根部隊包圍，主角死亡並觸發轉化程序。"

        return True, "非危險事件，預設安全。"