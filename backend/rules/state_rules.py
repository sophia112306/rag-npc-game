from typing import Dict, Tuple
from backend.schemas.game_state import GameState, StoryPhase


class StateRules:
    """遊戲數值更新、階段封頂與防護規則 (草案 v3 規格)"""

    @staticmethod
    def apply_delta(
        game_state: GameState,
        axis_delta: int = 0,
        usurp_delta: int = 0,
        relation_deltas: Dict[str, int] = None,
        phase_gained_relations: Dict[str, int] = None,
        is_event: bool = False
    ) -> Tuple[GameState, Dict[str, int]]:
        """
        將數值增減套用到 GameState，並執行：
        1. 階段封頂限制 (Cap Protection)
        2. 篡奪值兩段式攔截與警告機制 (Usurp Interception)
        3. 對話單一階段關係值防刷分 (+40 Limit)

        :param game_state: 當前遊戲狀態
        :param axis_delta: 主軸變更值 (-5 ~ +5)
        :param usurp_delta: 篡奪值變更值 (0 ~ +2)
        :param relation_deltas: 各 NPC 關係變更值
        :param phase_gained_relations: 當前階段各 NPC 已透過對話累積獲得的關係值
        :param is_event: 是否為固定事件套用 (固定事件不受單回合限制，但仍受階段封頂限制)
        :return: (更新後的 GameState, 更新後的 phase_gained_relations)
        """
        if relation_deltas is None:
            relation_deltas = {}
        if phase_gained_relations is None:
            phase_gained_relations = {}

        phase = game_state.story_phase

        # -----------------------------------------------------------------
        # 1. 階段封頂上限對照表
        # -----------------------------------------------------------------
        if phase == StoryPhase.ACT1_APPROACHING:
            axis_min, axis_max = -20, 20
            usurp_max = 20
        elif phase == StoryPhase.ACT2_MIDTERM:
            axis_min, axis_max = -50, 50
            usurp_max = 70
        elif phase in (StoryPhase.ACT3_FREEDOM, StoryPhase.ACT4_ENDING, StoryPhase.USURP_COUNTDOWN):
            axis_min, axis_max = -100, 100
            usurp_max = 100
        else:
            axis_min, axis_max = -100, 100
            usurp_max = 100

        # -----------------------------------------------------------------
        # 2. 更新主軸傾向值 (axis) 並執行邊界限制
        # -----------------------------------------------------------------
        new_axis = game_state.axis + axis_delta
        game_state.axis = max(axis_min, min(axis_max, new_axis))

        # -----------------------------------------------------------------
        # 3. 篡奪值 (usurp) 兩段式攔截與警告機制
        # -----------------------------------------------------------------
        target_usurp = game_state.usurp + usurp_delta

        # 先受限於當前階段的最大上限
        target_usurp = min(usurp_max, target_usurp)

        # 攔截規則 A: 首次欲跨越 75 時，強制扣留於 75 並觸發警告標記
        if target_usurp >= 75 and not game_state.warning_triggered:
            game_state.usurp = 75
            game_state.warning_triggered = True
            game_state.flags["warning_triggered"] = True
        else:
            # 攔截規則 B: 警告觸發後的 5 回合冷卻期內，最高卡在 89
            # (假設宣告冷卻由 phase_turns 或專門冷卻次數控管，此處實現 <= 89 攔截)
            if game_state.warning_triggered and game_state.usurp < 90 and target_usurp >= 90:
                # 只有在特定條件下解鎖 90+，否則冷卻期間最高限制在 89
                if game_state.flags.get("usurp_unlocked_90", False):
                    game_state.usurp = min(100, target_usurp)
                else:
                    game_state.usurp = 89
            else:
                game_state.usurp = max(0, min(100, target_usurp))

        # 若篡奪值達到 90 且尚未進入倒數，觸發狀態切換標籤
        if game_state.usurp >= 90 and game_state.story_phase == StoryPhase.ACT3_FREEDOM:
            game_state.story_phase = StoryPhase.USURP_COUNTDOWN
            if game_state.usurp_countdown_turns > 3:
                game_state.usurp_countdown_turns = 3

        # -----------------------------------------------------------------
        # 4. NPC 關係值更新與單一階段 +40 防刷分限制
        # -----------------------------------------------------------------
        for npc_id, delta in relation_deltas.items():
            if npc_id not in game_state.npc_states:
                # 動態支援其他次要 NPC，預設初始值為 50
                from backend.schemas.game_state import NPCState
                game_state.npc_states[npc_id] = NPCState(npc_id=npc_id, name=npc_id, relation=50)

            npc = game_state.npc_states[npc_id]

            if is_event:
                # 固定事件產生的數值不受單階段 +40 防刷分限制
                npc.relation = max(0, min(100, npc.relation + delta))
            else:
                # 一般對話：單一角色在單一階段靠對話最多 +40
                current_gained = phase_gained_relations.get(npc_id, 0)

                if delta > 0:
                    allowed_gain = max(0, 40 - current_gained)
                    actual_delta = min(delta, allowed_gain)
                    phase_gained_relations[npc_id] = current_gained + actual_delta
                else:
                    actual_delta = delta  # 扣分不設防刷上限

                npc.relation = max(0, min(100, npc.relation + actual_delta))

        return game_state, phase_gained_relations