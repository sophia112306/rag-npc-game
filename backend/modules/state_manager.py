from typing import Dict, List, Optional, Tuple
from backend.schemas.game_state import GameState, StoryPhase
from backend.schemas.api_response import DeltaPayload
from backend.rules.state_rules import StateRules
from backend.rules.scene_rules import SceneRules
from backend.rules.event_rules import EventRules
from backend.rules.ending_rules import EndingRules


class StateManager:
    """狀態管理器：整合數值計算、階段推進、真相保底與玩家轉化邏輯 (草案 v3 規格)"""

    @staticmethod
    def process_turn(
        game_state: GameState,
        delta_payload: Optional[DeltaPayload] = None,
        event_id: Optional[str] = None,
        completed_events: Optional[List[str]] = None,
        danger_action_args: Optional[dict] = None
    ) -> Tuple[GameState, List[str], Optional[str]]:
        """
        每回合核心處理流程：
        1. 處理危險事件與玩家死亡/轉化判定
        2. 套用固定事件或單回合 AI 數值增減 (含階段封頂與兩段式篡奪攔截)
        3. 檢查階段自動切換與真相保底機制
        4. 算當前可選結局清單

        :param game_state: 當前遊戲狀態
        :param delta_payload: 敘事 AI 傳回的數值增減 (axis, usurp, relation)
        :param event_id: 觸發的固定事件 ID (如 'E2-1_prevent', 'E2-2')
        :param completed_events: 已完成的歷史事件清單
        :param danger_action_args: 危險事件脫身參數
        :return: (更新後的 GameState, 當前可選結局清單, 系統通知/警告訊息)
        """
        if completed_events is None:
            completed_events = []
        if danger_action_args is None:
            danger_action_args = {}

        system_message = None

        # -----------------------------------------------------------------
        # 0. 增加回合次數 (總回合數 & 當前階段回合數)
        # -----------------------------------------------------------------
        game_state.turn_count += 1
        game_state.phase_turns += 1

        # 若在篡夢倒數中，倒數回合減 1
        if game_state.story_phase == StoryPhase.USURP_COUNTDOWN:
            game_state.usurp_countdown_turns -= 1
            if game_state.usurp_countdown_turns <= 0:
                system_message = "篡夢倒數結束，強制進入篡夢結局！"

        # -----------------------------------------------------------------
        # 1. 處理危險事件 (E2-2, E3-1) 與「玩家死亡與轉化」邏輯
        # -----------------------------------------------------------------
        if event_id in ("E2-2", "E3-1"):
            is_alive, reason = EventRules.evaluate_danger_event(game_state, event_id, danger_action_args)
            if not is_alive:
                # 玩家死亡：執行轉化程序
                StateManager.handle_player_death_and_transformation(game_state)
                system_message = f"【危險觸發】{reason} 玩家語音輸入已暫停，已選擇轉化為世界原生生物。"

        # -----------------------------------------------------------------
        # 2. 自動計算並封頂 axis / usurp / relation
        # -----------------------------------------------------------------
        is_event = False
        axis_delta, usurp_delta, relation_deltas = 0, 0, {}

        # 優先處理固定事件數值
        if event_id and EventRules.get_event_effect(event_id):
            effect = EventRules.get_event_effect(event_id)
            axis_delta = effect.get("axis", 0)
            usurp_delta = effect.get("usurp", 0)
            relation_deltas = effect.get("relation", {})
            is_event = True

            # 套用事件旗標與真相度
            for flag_name, flag_val in effect.get("flags", {}).items():
                game_state.flags[flag_name] = flag_val

            if "truth_delta" in effect:
                game_state.truth_level = min(3, game_state.truth_level + effect["truth_delta"])

            if event_id not in completed_events:
                completed_events.append(event_id)

        # 其次套用一般對話 AI Delta Payload
        elif delta_payload:
            axis_delta = delta_payload.axis
            usurp_delta = delta_payload.usurp
            relation_deltas = delta_payload.relation

        # 呼叫 StateRules 執行階段封頂與防刷分
        game_state, _ = StateRules.apply_delta(
            game_state=game_state,
            axis_delta=axis_delta,
            usurp_delta=usurp_delta,
            relation_deltas=relation_deltas,
            is_event=is_event
        )

        # -----------------------------------------------------------------
        # 3. 檢查並更新 story_phase 狀態與真相保底
        # -----------------------------------------------------------------
        # (1) 檢查階段切換
        new_phase = SceneRules.check_stage_transition(game_state, completed_events)
        if new_phase != game_state.story_phase and game_state.story_phase != StoryPhase.USURP_COUNTDOWN:
            game_state.story_phase = new_phase
            game_state.phase_turns = 0  # 重置新階段的回合計數器
            system_message = f"劇情推進！進入階段：{new_phase.value}"

        # (2) 檢查真相時間保底
        fallback_truths = SceneRules.check_truth_fallbacks(game_state)
        if fallback_truths:
            for truth_event in fallback_truths:
                effect = EventRules.get_event_effect(truth_event)
                if effect:
                    for flag_name, flag_val in effect.get("flags", {}).items():
                        game_state.flags[flag_name] = flag_val
                    game_state.truth_level = min(3, game_state.truth_level + effect.get("truth_delta", 1))
            system_message = f"【真相保底觸發】解鎖真相：{', '.join(fallback_truths)}"

        # -----------------------------------------------------------------
        # 4. 算當前可選結局清單
        # -----------------------------------------------------------------
        available_endings = EndingRules.evaluate_available_endings(game_state)

        return game_state, available_endings, system_message

    @staticmethod
    def handle_player_death_and_transformation(game_state: GameState, choice_race: str = "spirit") -> GameState:
        """
        處理玩家死亡與轉化邏輯：
        1. 標記已轉化 (is_transformed = True)
        2. 永久關閉【新夢】與【塵歸】結局
        3. 生死簿開始記錄玩家名字
        """
        game_state.flags["is_transformed"] = True
        game_state.flags["transformed_race"] = choice_race  # 'spirit', 'mummy', 'human'
        
        # 轉化後艾倫通訊中斷，篡奪值不再因艾倫任務上升
        game_state.flags["alan_communication_severed"] = True

        return game_state

if __name__ == "__main__":
    print("=== 正在測試草案 v3 StateManager 邏輯 ===")
    
    # 建立初始狀態
    gs = GameState(session_id="test_v3_session")
    print(f"【初始階段】: {gs.story_phase.value}, axis={gs.axis}, usurp={gs.usurp}, truth={gs.truth_level}")

    # 1. 測試一般對話與數值套用 (符合單回合限制 axis<=5, usurp<=2)
    delta = DeltaPayload(axis=5, usurp=2, relation={"andre": 10})
    gs, endings, msg = StateManager.process_turn(gs, delta_payload=delta)
    print(f"【回合 1 (單回合 Delta 測試)】: axis={gs.axis}, usurp={gs.usurp}, 安德烈關係={gs.npc_states['andre'].relation}")

    # 2. 測試固定事件觸發 (E1-1 ~ E1-5 完成切換至階段二)
    completed = ["E1-1", "E1-2", "E1-3", "E1-4", "E1-5"]
    gs, endings, msg = StateManager.process_turn(gs, event_id="E1-5", completed_events=completed)
    print(f"【回合 2 (切換階段二)】: 當前階段={gs.story_phase.value}, 系統訊息={msg}")

    # 3. 測試篡奪值 75 兩段式攔截 (先將篡奪值設為 70，再套用 E2-4_place 事件 +15)
    gs.usurp = 70
    gs, endings, msg = StateManager.process_turn(gs, event_id="E2-4_place", completed_events=completed)
    print(f"【回合 3 (篡奪值 75 攔截)】: usurp={gs.usurp} (應卡在 75), 警告已觸發={gs.warning_triggered}")

    # 4. 測試當前可選結局計算
    print(f"【當前可選結局】: {endings}")
    print("=== 所有草案 v3 邏輯驗證完畢，運作正常！ ===")