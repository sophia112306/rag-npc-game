from typing import Dict, Tuple
from backend.schemas.game_state import GameState, StoryPhase


class StateRules:
    """遊戲數值更新、階段封頂與防護規則 (草案 v3 規格)"""

    @staticmethod
    def apply_delta(
        game_state: GameState,
        axis_delta: int = 0,
        usurp_delta: int = 0,
        truth_delta: int = 0,
        relation_deltas: Dict[str, int] = None,
        phase_gained_relations: Dict[str, int] = None,
        is_event: bool = False
    ) -> Tuple[GameState, Dict[str, int]]:
        """
        將數值增減套用到 GameState，並執行：
        1. 階段封頂限制 (Cap Protection) 與階段四鎖定
        2. 篡奪值兩段式攔截、警告冷卻與倒數不下降機制
        3. 真相度 (truth_level) 累加與上限 3 限制
        4. 對話單一階段關係值防刷分 (+40 Limit)
        """
        if relation_deltas is None:
            relation_deltas = {}
        if phase_gained_relations is None:
            phase_gained_relations = {}

        phase = game_state.story_phase

        # -----------------------------------------------------------------
        # 0. 更新真相度 (truth_level，範圍 0 ~ 3)
        # -----------------------------------------------------------------
        if truth_delta != 0:
            game_state.truth_level = max(0, min(3, game_state.truth_level + truth_delta))

        # -----------------------------------------------------------------
        # 1. 階段四 (ACT4_ENDING) 鎖定主軸與篡奪值不再變動
        # -----------------------------------------------------------------
        if phase != StoryPhase.ACT4_ENDING:
            # 階段封頂上限對照表
            if phase == StoryPhase.ACT1_APPROACHING:
                axis_min, axis_max = -20, 20
                usurp_max = 20
            elif phase == StoryPhase.ACT2_MIDTERM:
                axis_min, axis_max = -50, 50
                usurp_max = 70
            else:
                axis_min, axis_max = -100, 100
                usurp_max = 100

            # -------------------------------------------------------------
            # 2. 更新主軸傾向值 (axis)、邊界限制與「同一立場 3 回合內只計一次」
            # -------------------------------------------------------------
            if not is_event and axis_delta != 0:
                current_sign = 1 if axis_delta > 0 else -1
                if current_sign in game_state.recent_axis_signs[-2:]:
                    effective_axis_delta = 0
                else:
                    effective_axis_delta = axis_delta
                game_state.recent_axis_signs.append(current_sign)
                game_state.recent_axis_signs = game_state.recent_axis_signs[-3:]
            else:
                effective_axis_delta = axis_delta
                if not is_event:
                    game_state.recent_axis_signs.append(0)
                    game_state.recent_axis_signs = game_state.recent_axis_signs[-3:]

            new_axis = game_state.axis + effective_axis_delta
            game_state.axis = max(axis_min, min(axis_max, new_axis))

            # -------------------------------------------------------------
            # 3. 篡奪值 (usurp) 攔截、警告冷卻與倒數不下降機制
            # -------------------------------------------------------------
            # 規則：一旦達 90 進入篡夢倒數，此後不再下降
            if (phase == StoryPhase.USURP_COUNTDOWN or game_state.usurp >= 90) and usurp_delta < 0:
                effective_usurp_delta = 0
            else:
                effective_usurp_delta = usurp_delta

            target_usurp = min(usurp_max, game_state.usurp + effective_usurp_delta)

            # 攔截規則 A: 首次欲跨越 75 時，強制扣留於 75 並啟動 5 回合冷卻
            if target_usurp >= 75 and not game_state.warning_triggered:
                game_state.usurp = 75
                game_state.warning_triggered = True
                game_state.warning_cooldown_turns = 5
                game_state.flags["warning_triggered"] = True
            else:
                # 攔截規則 B: 警告觸發後的 5 回合冷卻期內，最高卡在 89
                in_cooldown = game_state.warning_cooldown_turns > 0
                if game_state.warning_triggered and in_cooldown and target_usurp >= 90:
                    game_state.usurp = 89
                else:
                    game_state.usurp = max(0, min(100, target_usurp))

            # 若篡奪值達到 90 且位於階段三，觸發篡夢倒數狀態切換
            if game_state.usurp >= 90 and game_state.story_phase == StoryPhase.ACT3_FREEDOM:
                game_state.story_phase = StoryPhase.USURP_COUNTDOWN
                if game_state.usurp_countdown_turns > 3:
                    game_state.usurp_countdown_turns = 3

        # -----------------------------------------------------------------
        # 4. NPC 關係值更新與單一階段 +40 防刷分限制
        # -----------------------------------------------------------------
        for npc_id, delta in relation_deltas.items():
            if npc_id not in game_state.npc_states:
                from backend.schemas.game_state import NPCState
                game_state.npc_states[npc_id] = NPCState(npc_id=npc_id, name=npc_id, relation=50)

            npc = game_state.npc_states[npc_id]

            if is_event:
                npc.relation = max(0, min(100, npc.relation + delta))
            else:
                current_gained = phase_gained_relations.get(npc_id, 0)

                if delta > 0:
                    allowed_gain = max(0, 40 - current_gained)
                    actual_delta = min(delta, allowed_gain)
                    phase_gained_relations[npc_id] = current_gained + actual_delta
                else:
                    actual_delta = delta

                npc.relation = max(0, min(100, npc.relation + actual_delta))

        return game_state, phase_gained_relations