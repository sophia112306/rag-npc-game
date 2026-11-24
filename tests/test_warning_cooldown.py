"""規格 v3：篡奪值先停在 75 觸發警告事件 W，之後至少 5 回合最高只到 89。"""

from backend.rules.state_rules import StateRules
from backend.schemas.game_state import GameState, StoryPhase


def act3_state(**overrides) -> GameState:
    return GameState(session_id="cooldown", story_phase=StoryPhase.ACT3_FREEDOM, **overrides)


def test_crossing_75_stops_there_and_starts_a_five_turn_cooldown() -> None:
    state = act3_state(usurp=70)

    StateRules.apply_delta(state, usurp_delta=20, is_event=True)

    assert state.usurp == 75
    assert state.warning_triggered is True
    assert state.warning_cooldown_turns == 5


def test_cooldown_caps_usurp_at_89_until_it_runs_out() -> None:
    state = act3_state(usurp=75, warning_triggered=True, warning_cooldown_turns=5)

    StateRules.apply_delta(state, usurp_delta=20, is_event=True)
    assert state.usurp == 89
    assert state.story_phase == StoryPhase.ACT3_FREEDOM

    for _ in range(5):
        StateRules.tick_warning_cooldown(state)
    assert state.warning_cooldown_turns == 0

    StateRules.apply_delta(state, usurp_delta=2, is_event=True)
    assert state.usurp == 91
    assert state.story_phase == StoryPhase.USURP_COUNTDOWN


def test_cooldown_never_goes_below_zero() -> None:
    state = act3_state(warning_cooldown_turns=1)

    StateRules.tick_warning_cooldown(state)
    StateRules.tick_warning_cooldown(state)

    assert state.warning_cooldown_turns == 0
