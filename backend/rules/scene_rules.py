from typing import List, Optional
from backend.schemas.game_state import GameState, StoryPhase


# 固定選項主線（demo_story）的換階段點。主線不是用 E1～E3 事件推進，
# 所以把規格 v3 的四個階段對應到主線的劇情節點：
# - 階段二：兩區調查完後第一次前往邊境廢墟（E2-3 屬於中期事件）
# - 階段三：進入記憶圖書館，開始揭露真相 A／B／C
# - 進入維塔源頭暫時維持階段三：第 2 題「控制」仍是現行的篡夢路線（篡奪值 +90），
#   階段四會鎖住篡奪值；等階段三的篡夢倒數流程接上後再改成階段四
STORY_CHOICE_PHASES: dict[str, StoryPhase] = {
    "preview_border_ruins": StoryPhase.ACT2_MIDTERM,
    "enter_memory_library_with_map": StoryPhase.ACT3_FREEDOM,
    "enter_memory_library_with_elders": StoryPhase.ACT3_FREEDOM,
    "enter_memory_library_alone": StoryPhase.ACT3_FREEDOM,
    "enter_veta_source": StoryPhase.ACT3_FREEDOM,
}
# 規格 v3 各階段的最高回合。到達時只提示下一步，不強制換階段（主線靠劇情節點推進）。
PHASE_TURN_LIMITS: dict[StoryPhase, int] = {
    StoryPhase.ACT1_APPROACHING: 20,
    StoryPhase.ACT2_MIDTERM: 30,
    StoryPhase.ACT3_FREEDOM: 30,
}
PHASE_ORDER = (
    StoryPhase.ACT1_APPROACHING,
    StoryPhase.ACT2_MIDTERM,
    StoryPhase.ACT3_FREEDOM,
    StoryPhase.ACT4_ENDING,
)


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
    def phase_after_story_choice(game_state: GameState, choice_id: str) -> StoryPhase:
        """主線選項完成後應處的階段。階段只會往前走；篡夢倒數與結局期不受影響。"""

        current = game_state.story_phase
        target = STORY_CHOICE_PHASES.get(choice_id)
        if target is None or current not in PHASE_ORDER:
            return current
        if PHASE_ORDER.index(target) <= PHASE_ORDER.index(current):
            return current
        return target

    @staticmethod
    def phase_turn_limit_reached(game_state: GameState) -> bool:
        """目前階段的回合數是否已達規格 v3 的最高回合。"""

        limit = PHASE_TURN_LIMITS.get(game_state.story_phase)
        return limit is not None and game_state.phase_turns >= limit

    @staticmethod
    def enter_phase(game_state: GameState, phase: StoryPhase) -> bool:
        """切換階段並重置階段回合數與「每階段」防刷分計數器。回傳是否有切換。"""

        if phase == game_state.story_phase:
            return False
        from backend.rules.state_rules import StateRules

        game_state.story_phase = phase
        game_state.phase_turns = 0
        StateRules.reset_dialogue_counters(game_state)
        return True

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