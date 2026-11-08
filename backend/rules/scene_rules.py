from typing import List, Optional
from backend.schemas.game_state import GameState, StoryPhase


class SceneRules:
    """階段推進與真相保底規則 (草案 v3 規格)"""

    @staticmethod
    def check_stage_transition(game_state: GameState, completed_events: List[str]) -> StoryPhase:
        """
        檢查並判定是否觸發階段自動切換。

        :param game_state: 當前遊戲狀態
        :param completed_events: 已完成的固定事件 ID 清單 (例如 ['E1-1', 'E1-2', ...])
        :return: 切換後的 StoryPhase (若未符合切換條件則返回當前 phase)
        """
        phase = game_state.story_phase
        turns = game_state.phase_turns  # 當前階段已消耗的回合數

        # -----------------------------------------------------------------
        # 1. 階段一 -> 階段二
        # 條件：完成 E1-1 ~ E1-5 或當前階段滿 20 回合
        # -----------------------------------------------------------------
        if phase == StoryPhase.ACT1_APPROACHING:
            e1_events = {"E1-1", "E1-2", "E1-3", "E1-4", "E1-5"}
            e1_completed = e1_events.issubset(set(completed_events))

            if e1_completed or turns >= 20:
                return StoryPhase.ACT2_MIDTERM

        # -----------------------------------------------------------------
        # 2. 階段二 -> 階段三
        # 條件：完成任意 3 個中期事件 (E2-1~E2-4) 且 (truth_level >= 1 或 usurp >= 50)
        # 限制：最低 10 回合、最高 30 回合 (滿 30 回合強制切換)
        # -----------------------------------------------------------------
        elif phase == StoryPhase.ACT2_MIDTERM:
            e2_events = {"E2-1", "E2-2", "E2-3", "E2-4"}
            completed_e2_count = len(e2_events.intersection(set(completed_events)))

            condition_met = (completed_e2_count >= 3) and (
                game_state.truth_level >= 1 or game_state.usurp >= 50
            )

            # 最低 10 回合約束
            if turns >= 10 and condition_met:
                return StoryPhase.ACT3_FREEDOM

            # 最高 30 回合保底切換
            if turns >= 30:
                return StoryPhase.ACT3_FREEDOM

        # -----------------------------------------------------------------
        # 3. 階段三 -> 階段四 (進入結局期)
        # 條件：truth_level == 3 且滿 10 回合 (或上限 30 回合)
        # -----------------------------------------------------------------
        elif phase == StoryPhase.ACT3_FREEDOM:
            # 篡夢倒數狀態優先，不在此切換至 Act4
            if turns >= 10 and game_state.truth_level == 3:
                return StoryPhase.ACT4_ENDING

            # 最高 30 回合保底進入階段四
            if turns >= 30:
                return StoryPhase.ACT4_ENDING

        return phase

    @staticmethod
    def check_truth_fallbacks(game_state: GameState) -> List[str]:
        """
        真相保底觸發器 (Truth Fallbacks)
        當玩家因為早期選擇或回合數過長而未獲取真相時，主動回傳需強制觸發的真相事件 ID。

        :param game_state: 當前遊戲狀態
        :return: 需在下一回合強制觸發的真相事件 ID 清單 (如 ['Truth_A'])
        """
        triggered_truths = []
        phase = game_state.story_phase
        turns = game_state.phase_turns

        # 真相 A（生死簿的空白頁）：階段二滿 30 回合保底觸發
        if phase == StoryPhase.ACT2_MIDTERM and turns >= 30:
            if not game_state.flags.get("truth_a_unlocked", False):
                triggered_truths.append("Truth_A")

        # 真相 B（千年前的入侵紀錄）：階段三滿 15 回合保底觸發
        if phase == StoryPhase.ACT3_FREEDOM and turns >= 15:
            if not game_state.flags.get("truth_b_unlocked", False):
                triggered_truths.append("Truth_B")

        # 真相 C（艾倫的破綻）：階段三滿 20 回合保底觸發
        if phase == StoryPhase.ACT3_FREEDOM and turns >= 20:
            if not game_state.flags.get("truth_c_unlocked", False):
                triggered_truths.append("Truth_C")

        return triggered_truths