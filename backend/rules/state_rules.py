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

# 關係值 → NPC prompt 的信任度（與訓練資料的「信任度：低／中／高／至高信任」一致）。
# 只有規格定義關係值的三個角色有信任度；其他角色的關係值不會變動，不傳。
# 每個角色是 (上限, 等級) 由低到高排列；超過最後一個上限的是最高等級。
TRUST_TIERS: Dict[str, Tuple[Tuple[int, str], ...]] = {
    # 40 起會援助主角，60 解鎖隱藏洞穴與引薦
    "andre": ((39, "低"), (59, "中"), (100, "高")),
    # 維達利亞角色規範與訓練資料：t<40 低、40～59 中、≥60 高
    "vidalia": ((39, "低"), (59, "中"), (100, "高")),
    # 門梅司文托角色規範：≤10 閉門期、11～59 觀察期、60～79 解鎖期、≥80 結局交付期
    "menmesvento": ((10, "低"), (59, "中"), (79, "高"), (100, "至高")),
}

# 角色規範的行為模式（傳給 NPC 的文字描述，不含數值）
MENMESVENTO_MODES = {
    "低": "閉門期：態度冰冷、戒備且排斥，拒絕提供任何關鍵情報或協助，直接下逐客令。",
    "中": "觀察期：冷靜、疏離，帶隱者的超然與疲憊；只談宏觀世界觀與思辨，不透露生死簿的秘密，被索求真相時會說出信任條件。",
    "高": "解鎖期：沉穩、凝重並帶一絲寄望，認可主角是打破循環的同行者，願意坦承對無盡輪迴的厭倦與對涅槃的追求。",
    "至高": "結局交付期：悲憫、託付與決絕，把打破循環的希望寄託於主角；探討生命的真實與死亡的必要，但把抉擇交給主角，不斷言結局。",
}
VIDALIA_MODES = {
    "ending": "結局期：平靜、釋懷，溫柔中帶一絲宿命的蒼涼；不斷言結局，把選擇權交給主角。",
    "attached": "依附：從疏離轉為脆弱、溫柔，試圖把主角留在夢境中，反對破壞結界。",
    "wavering": "動搖：從抵抗轉為困惑，吐露其實不想讓世界改變的真心，卻對主角的選擇感到迷茫。",
    "observer": "好奇的觀察者：千年歲月的倦怠與旁觀，優雅而疏離、回應簡短；主角索取核心情報時會笑著點出信任條件。",
}


def npc_trust_tier(npc_id: str, relation: int) -> str | None:
    """把關係值換算成 NPC 看得到的信任度；NPC 模型不會拿到關係值本身。"""

    tiers = TRUST_TIERS.get(npc_id)
    if tiers is None:
        return None
    for upper, label in tiers:
        if relation <= upper:
            return label
    return tiers[-1][1]


def npc_behavior_mode(npc_id: str, relation: int, axis: int, phase: StoryPhase) -> str | None:
    """依角色規範推出 NPC 目前的行為模式（文字），沒有規範的角色回傳 None。

    維達利亞依規格 v3「關係值 × 主軸」推出：關係 60 以上且主軸 ≤ −20 依附、
    主軸 ≥ +20 動搖，其餘是好奇的觀察者；結局期改為交出選擇權。
    """

    if npc_id == "menmesvento":
        tier = npc_trust_tier(npc_id, relation)
        return MENMESVENTO_MODES.get(tier) if tier else None
    if npc_id == "vidalia":
        if phase == StoryPhase.ACT4_ENDING:
            return VIDALIA_MODES["ending"]
        if relation >= 60 and axis <= -20:
            return VIDALIA_MODES["attached"]
        if relation >= 60 and axis >= 20:
            return VIDALIA_MODES["wavering"]
        return VIDALIA_MODES["observer"]
    return None


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
        is_event: bool = False,
        axis_stance: str | None = None,
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
            #    敘事 AI 有給立場類別時，以類別判斷「同一立場」（不同理由可各自累積）；
            #    沒有類別時退回以正負號判斷。只記錄真正被計算的那一次，
            #    所以連續重複同一立場時，每 3 回合會再計算一次。
            counted_sign, counted_stance = 0, None
            if not is_event and axis_delta != 0:
                current_sign = 1 if axis_delta > 0 else -1
                if axis_stance:
                    repeated = axis_stance in game_state.recent_axis_stances[-2:]
                else:
                    repeated = current_sign in game_state.recent_axis_signs[-2:]
                effective_axis_delta = 0 if repeated else axis_delta
                if not repeated:
                    counted_sign, counted_stance = current_sign, axis_stance
            else:
                effective_axis_delta = axis_delta
            if not is_event:
                game_state.recent_axis_signs = (game_state.recent_axis_signs + [counted_sign])[-3:]
                game_state.recent_axis_stances = (
                    game_state.recent_axis_stances + [counted_stance]
                )[-3:]

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
    def tick_warning_cooldown(game_state: GameState) -> None:
        """規格 v3：警告事件 W 之後至少 5 回合，篡奪值最高只到 89。每過一回合倒數一次。"""

        if game_state.warning_cooldown_turns > 0:
            game_state.warning_cooldown_turns -= 1

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
        axis_stance: str | None = None,
    ) -> DialogueDeltaResult:
        """
        套用敘事 AI 對一句玩家發言提出的數值變化。AI 的數字只是提案，這裡依規格 v3 執行：
        1. 單回合上限：主軸 ±5、關係值 ±10、篡奪值 0～+2（對話不會降低篡奪值）
        2. 只接受安德烈、維達利亞、門梅司文托三個關係值，其他 ID 一律忽略
        3. 同一句話 3 回合內只計一次；同一立場（有類別時看類別，否則看正負號）3 回合內只計一次主軸
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
            axis_stance=axis_stance if axis else None,
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