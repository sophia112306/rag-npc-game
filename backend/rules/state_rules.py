from dataclasses import dataclass, field
import re
from typing import Dict, Tuple
from backend.schemas.game_state import GameState, StoryPhase


# 規格 v3「數值規格」與「防呆與保底」中，只適用於自由對話（敘事 AI 判讀）的限制。
# 事件的數值由 EventRules 直接套用，不受這些限制，但仍受 apply_delta 的階段封頂。
DIALOGUE_RELATION_NPCS = ("andre", "vidalia", "menmesvento")  # 規格只定義這三個關係值
DIALOGUE_AXIS_LIMIT = 5             # 主軸：對話每回合 ±0～5
DIALOGUE_RELATION_LIMIT = 10        # 關係值：對話每回合 ±0～10
DIALOGUE_USURP_LIMIT = 2            # 篡奪值：刻意激怒或逼迫 NPC 每回合 +2
PHASE_USURP_DIALOGUE_CAP = 10       # 篡奪值：靠激怒每階段最多 +10
RECENT_DIALOGUE_WINDOW = 3          # 同一句話 3 回合內只計一次


@dataclass(frozen=True)
class DialogueDeltaResult:
    """一次對話判讀實際生效的數值（經過所有限制之後）。"""

    axis: int = 0
    usurp: int = 0
    relation: Dict[str, int] = field(default_factory=dict)
    duplicate_message: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.axis or self.usurp or any(self.relation.values()))


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, int(value)))


def normalize_dialogue_message(message: str) -> str:
    """去掉空白與標點後比對「同一句話」；中文字元保留。"""

    return re.sub(r"[\W_]+", "", message or "").lower()


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

    @staticmethod
    def reset_dialogue_counters(game_state: GameState) -> None:
        """換階段時把「每階段」的對話防刷分計數器歸零。"""

        game_state.phase_usurp_dialogue_gain = 0
        game_state.phase_relation_dialogue_gain = {npc_id: 0 for npc_id in DIALOGUE_RELATION_NPCS}
        game_state.dialogue_counters_phase = game_state.story_phase

    @staticmethod
    def apply_dialogue_delta(
        game_state: GameState,
        axis_delta: int = 0,
        usurp_delta: int = 0,
        relation_deltas: Dict[str, int] | None = None,
        player_message: str = "",
    ) -> DialogueDeltaResult:
        """
        套用敘事 AI 對一句玩家發言提出的數值變化。AI 的數字只是提案，這裡依規格 v3 執行：
        1. 單回合上限：主軸 ±5、關係值 ±10、篡奪值 0～+2（對話不會降低篡奪值）
        2. 只接受安德烈、維達利亞、門梅司文托三個關係值，其他 ID 一律忽略
        3. 同一句話 3 回合內只計一次（同一立場由 apply_delta 的主軸符號規則處理）
        4. 每階段靠對話：每個角色關係值最多 +40、篡奪值最多 +10
        5. 再交給 apply_delta 執行階段封頂、75 攔截與倒數規則
        """

        if game_state.dialogue_counters_phase != game_state.story_phase:
            StateRules.reset_dialogue_counters(game_state)

        normalized = normalize_dialogue_message(player_message)
        duplicate = bool(normalized) and normalized in game_state.recent_dialogue_messages
        if normalized:
            game_state.recent_dialogue_messages = (
                game_state.recent_dialogue_messages + [normalized]
            )[-RECENT_DIALOGUE_WINDOW:]

        axis = _clamp(axis_delta, -DIALOGUE_AXIS_LIMIT, DIALOGUE_AXIS_LIMIT)
        usurp = _clamp(usurp_delta, 0, DIALOGUE_USURP_LIMIT)
        usurp = min(usurp, max(0, PHASE_USURP_DIALOGUE_CAP - game_state.phase_usurp_dialogue_gain))
        relations = {
            npc_id: _clamp(delta, -DIALOGUE_RELATION_LIMIT, DIALOGUE_RELATION_LIMIT)
            for npc_id, delta in (relation_deltas or {}).items()
            if npc_id in DIALOGUE_RELATION_NPCS and npc_id in game_state.npc_states and delta
        }
        if duplicate:
            axis, usurp, relations = 0, 0, {}

        before_axis = game_state.axis
        before_usurp = game_state.usurp
        before_relations = {npc_id: game_state.npc_states[npc_id].relation for npc_id in relations}

        _, gained = StateRules.apply_delta(
            game_state,
            axis_delta=axis,
            usurp_delta=usurp,
            relation_deltas=relations,
            phase_gained_relations=dict(game_state.phase_relation_dialogue_gain),
            is_event=False,
        )
        game_state.phase_relation_dialogue_gain = gained

        applied_usurp = game_state.usurp - before_usurp
        if applied_usurp > 0:
            game_state.phase_usurp_dialogue_gain += applied_usurp

        return DialogueDeltaResult(
            axis=game_state.axis - before_axis,
            usurp=applied_usurp,
            relation={
                npc_id: game_state.npc_states[npc_id].relation - before
                for npc_id, before in before_relations.items()
            },
            duplicate_message=duplicate,
        )