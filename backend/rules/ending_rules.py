from typing import List
from backend.schemas.game_state import GameState, StoryPhase


class EndingRules:
    """草案 v3 結局條件與可達性判定規則"""

    @staticmethod
    def evaluate_available_endings(game_state: GameState) -> List[str]:
        """
        根據當前遊戲狀態（軸線區間、真相度、NPC 關係值、旗標），
        實時算出當前可選的 1~3 個結局清單。

        :param game_state: 當前遊戲狀態
        :return: 可選結局名稱清單，如 ['長眠', '塵歸']
        """
        available: List[str] = []

        # 取出判定所需的關鍵欄位
        axis = game_state.axis
        truth_level = game_state.truth_level
        phase = game_state.story_phase

        # NPC 關係值
        vidalia_rel = game_state.npc_states.get("vidalia").relation if "vidalia" in game_state.npc_states else 0
        menmesvento_rel = game_state.npc_states.get("menmesvento").relation if "menmesvento" in game_state.npc_states else 0

        # 關鍵旗標
        has_dust_token = game_state.flags.get("has_dust_token", False)
        is_transformed = game_state.flags.get("is_transformed", False)

        # -----------------------------------------------------------------
        # 1. 解鎖硬性門檻檢查 (新夢 & 塵歸)
        # -----------------------------------------------------------------
        # 新夢硬性門檻：truth_level == 3 且 維達利亞 >= 60 且 門梅司文托 >= 60 且 未轉化
        can_unlock_new_dream = (
            truth_level == 3 and
            vidalia_rel >= 60 and
            menmesvento_rel >= 60 and
            not is_transformed
        )

        # 塵歸硬性門檻：truth_level == 3 且 持有塵歸令 (has_dust_token) 且 未轉化
        can_unlock_dust_return = (
            truth_level == 3 and
            has_dust_token and
            not is_transformed
        )

        # -----------------------------------------------------------------
        # 2. 篡夢倒數區 (USURP_COUNTDOWN 優先判定)
        # -----------------------------------------------------------------
        if phase == StoryPhase.USURP_COUNTDOWN or game_state.usurp >= 90:
            available.append("篡夢")
            if can_unlock_dust_return:
                available.append("塵歸")
            return available

        # -----------------------------------------------------------------
        # 3. 三區間演算法判定 (守夢區 / 中間區 / 醒夢區)
        # -----------------------------------------------------------------
        # (1) 守夢區 (axis <= -20)
        if axis <= -20:
            available.append("長眠")
            if can_unlock_dust_return:
                available.append("塵歸")

        # (2) 中間區 (-19 <= axis <= +19)
        elif -19 <= axis <= 19:
            available.append("長眠")
            
            # 醒來需門梅司文托 >= 40
            if menmesvento_rel >= 40:
                available.append("醒來")

            # 新夢只會在中間區且符合門檻時出現
            if can_unlock_new_dream:
                available.append("新夢")

        # (3) 醒夢區 (axis >= +20)
        elif axis >= 20:
            # 醒來需門梅司文托 >= 40；若未達，醒夢區退回長眠
            if menmesvento_rel >= 40:
                available.append("醒來")
            else:
                available.append("長眠")

            if can_unlock_dust_return:
                available.append("塵歸")

        return available