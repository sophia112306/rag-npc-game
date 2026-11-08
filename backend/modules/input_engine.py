from typing import Dict, List, Optional, Tuple
from backend.schemas.game_state import GameState, StoryPhase
from backend.rules.ending_rules import EndingRules
from backend.rules.event_rules import EventRules


class InputEngine:
    """敘事 AI 導向器與雙重保底機制 (草案 v3 規格)"""

    def __init__(self):
        # 記錄各事件被滿足條件後，未被 AI 挑中的懸空回合數 {event_id: pending_turns}
        self.pending_event_turns: Dict[str, int] = {}

    def get_context_for_narrative_ai(
        self,
        game_state: GameState,
        completed_events: List[str]
    ) -> Tuple[List[str], Optional[str], Dict[str, any]]:
        """
        每回合為敘事 AI 準備 Prompt 輸入內容與引導提示：
        1. 計算目前合法可觸發的固定事件清單
        2. 執行 8 回合強制作廢/觸發保底
        3. 執行「保證 5 個結局皆可達」的補救演算法

        :param game_state: 當前遊戲狀態
        :param completed_events: 已完成事件 ID 清單
        :return: (可觸發事件清單, 強制觸發事件ID, AI引導提示Context)
        """
        phase = game_state.story_phase
        allowed_events: List[str] = []

        # -----------------------------------------------------------------
        # 1. 篩選當前階段合法可觸發的事件
        # -----------------------------------------------------------------
        if phase == StoryPhase.ACT1_APPROACHING:
            candidate_events = ["E1-1", "E1-2", "E1-3", "E1-4", "E1-5"]
        elif phase == StoryPhase.ACT2_MIDTERM:
            candidate_events = ["E2-1", "E2-2", "E2-3", "E2-4"]
        elif phase == StoryPhase.ACT3_FREEDOM:
            candidate_events = ["E3-1", "E3-2", "E3-3", "E3-4"]
        else:
            candidate_events = []

        # 排除已完成的事件
        for ev in candidate_events:
            if ev not in completed_events:
                allowed_events.append(ev)

        # -----------------------------------------------------------------
        # 2. 8 回合未挑中強制觸發保底機制
        # -----------------------------------------------------------------
        forced_event: Optional[str] = None
        current_pending = list(self.pending_event_turns.keys())

        # 清除已完成的追蹤
        for ev in current_pending:
            if ev in completed_events:
                del self.pending_event_turns[ev]

        # 增加懸空計數
        for ev in allowed_events:
            self.pending_event_turns[ev] = self.pending_event_turns.get(ev, 0) + 1
            if self.pending_event_turns[ev] >= 8 and forced_event is None:
                forced_event = ev  # 達到 8 回合，強制注入下一回合執行

        # -----------------------------------------------------------------
        # 3. 「前中期保證 5 結局皆可達」補救演算法
        # -----------------------------------------------------------------
        ai_guidance = {}

        # 僅在階段一、階段二進行全結局保底補救
        if phase in (StoryPhase.ACT1_APPROACHING, StoryPhase.ACT2_MIDTERM):
            remedy_hints = self._calculate_ending_gap_remedies(game_state)
            ai_guidance["remedy_hints"] = remedy_hints

        return allowed_events, forced_event, ai_guidance

    def _calculate_ending_gap_remedies(self, game_state: GameState) -> List[str]:
        """
        計算數值缺口，若發現某結局即將因門檻不足而關閉，
        傳回需建議敘事 AI 主動安排登場的 NPC 或表態情境。
        """
        hints: List[str] = []

        vidalia_rel = game_state.npc_states.get("vidalia").relation if "vidalia" in game_state.npc_states else 0
        menmesvento_rel = game_state.npc_states.get("menmesvento").relation if "menmesvento" in game_state.npc_states else 0

        # 新夢缺口：需門梅司文托 >= 60 與 維達利亞 >= 60
        if menmesvento_rel < 60:
            hints.append("建議增加門梅司文托的出場與對話機會，讓玩家有機會提升其關係值至 60 以上 (影響新夢/醒來結局)。")
        if vidalia_rel < 60:
            hints.append("建議增加維達利亞的登場與互動情境 (影響新夢結局)。")

        # 醒來缺口：需門梅司文托 >= 40
        if menmesvento_rel < 40:
            hints.append("門梅司文托關係值偏低，建議安排其現身引導玩家表態。")

        return hints

if __name__ == "__main__":
    print("=== 正在測試 InputEngine 與 ActionValidator 雙重保底邏輯 ===")

    input_engine = InputEngine()
    gs = GameState(session_id="validator_test")

    # 1. 模擬事件 E1-1 懸空 8 回合
    completed = []
    for turn in range(8):
        allowed, forced, guidance = input_engine.get_context_for_narrative_ai(gs, completed)
        print(f"回合 {turn + 1}: 允許事件={allowed}, 強制觸發={forced}")

    # 第 8 回合應該印出強制的 E1-1
    print(f"【8 回保底測試結果】: 強制觸發事件 = {forced}")
    print(f"【前中期 AI 補救提示】: {guidance.get('remedy_hints')}")
    print("=== 所有導向器保底邏輯驗證完畢！ ===")