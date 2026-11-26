"""Deterministic Alan HUD messages derived from authoritative game state."""

from backend.schemas.alan_hud import AlanHud, AlanTone
from backend.schemas.game_state import GameState, StoryPhase


def _label(state: GameState) -> str:
    # Alan remains unnamed until the story has revealed enough truth to the
    # protagonist.  The HUD itself is still available from the opening turn.
    return "艾倫連線" if state.truth_level >= 2 else "視網膜連線"


def _calm_message(state: GameState) -> str:
    if state.truth_level >= 2:
        return "因果解析完成。下一步仍由你決定。"
    return "目標已建立。請沿路線收集異常資料。"


def build_alan_hud(state: GameState) -> AlanHud:
    """Project private state into a protagonist-only Alan HUD signal.

    The thresholds mirror the existing state rules: 50 marks an urgent
    deviation, 75 is the warning/interference boundary, and 90 starts the
    usurp countdown in Act 3.  No raw flags, NPC goals, or hidden lore are
    exposed here.
    """

    if state.flags.get("alan_communication_severed"):
        return AlanHud(
            visible=False,
            label="視網膜連線",
            display_value=state.usurp,
            tone="silent",
            message="連線已中斷。",
            persistent=True,
            event_key="alan:silent",
        )

    label = _label(state)
    usurp = state.usurp
    if state.story_phase == StoryPhase.USURP_COUNTDOWN or usurp >= 90:
        countdown = max(0, min(3, state.usurp_countdown_turns))
        return AlanHud(
            label=label,
            display_value=usurp,
            tone="override",
            message=(
                f"連線權限正在被覆寫。篡奪率 {usurp}%。"
                f"世界崩解倒數：{countdown} 回合。"
            ),
            persistent=True,
            countdown_turns=countdown,
            event_key="alan:override",
        )

    if state.warning_triggered or usurp >= 75:
        return AlanHud(
            label=label,
            display_value=usurp,
            tone="interference",
            message="警告：外部連線受到干擾。請維持任務方向。",
            persistent=True,
            event_key="alan:warning",
        )

    if usurp >= 50:
        return AlanHud(
            label=label,
            display_value=usurp,
            tone="urgent",
            message="偵測到世界規則偏移。請勿相信未驗證的聲音。",
            event_key="alan:urgent",
        )

    tone: AlanTone = "calm"
    return AlanHud(
        label=label,
        display_value=usurp,
        tone=tone,
        message=_calm_message(state),
        event_key="alan:calm",
    )
