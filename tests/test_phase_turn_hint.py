"""規格 v3 回合保底：階段停留到最高回合時，艾倫的視網膜訊息提示下一步，不強制換階段。"""

import pytest

from backend.content.alan_hud import build_alan_hud
from backend.rules.scene_rules import PHASE_TURN_LIMITS, SceneRules
from backend.schemas.game_state import GameState, StoryPhase
from backend.schemas.player_view import project_player_view


def stuck_state(phase: StoryPhase, turns: int, **kwargs) -> GameState:
    return GameState(
        session_id="stuck", current_scene_id="minglin", story_phase=phase, phase_turns=turns, **kwargs
    )


@pytest.mark.parametrize(
    ("phase", "limit"),
    [(StoryPhase.ACT1_APPROACHING, 20), (StoryPhase.ACT2_MIDTERM, 30), (StoryPhase.ACT3_FREEDOM, 30)],
)
def test_limit_follows_spec(phase, limit) -> None:
    assert PHASE_TURN_LIMITS[phase] == limit
    assert not SceneRules.phase_turn_limit_reached(stuck_state(phase, limit - 1))
    assert SceneRules.phase_turn_limit_reached(stuck_state(phase, limit))


def test_no_limit_in_ending_phase() -> None:
    assert not SceneRules.phase_turn_limit_reached(stuck_state(StoryPhase.ACT4_ENDING, 99))


def test_hud_nudges_with_the_current_objective_and_keeps_the_phase() -> None:
    state = stuck_state(StoryPhase.ACT1_APPROACHING, 20)

    view = project_player_view(state)

    assert view.alan_hud.tone == "calm"
    assert view.alan_hud.event_key == "alan:nudge:Act1_Approaching"
    assert view.alan_hud.message == f"任務進度停滯。{view.navigation.objective}"
    assert state.story_phase == StoryPhase.ACT1_APPROACHING


def test_hud_stays_normal_before_the_limit_or_without_a_next_step() -> None:
    assert build_alan_hud(stuck_state(StoryPhase.ACT1_APPROACHING, 19), next_step="下一步：x").event_key == "alan:calm"
    assert build_alan_hud(stuck_state(StoryPhase.ACT1_APPROACHING, 20)).event_key == "alan:calm"


def test_usurp_warnings_take_priority_over_the_nudge() -> None:
    state = stuck_state(StoryPhase.ACT3_FREEDOM, 30, usurp=75, warning_triggered=True)

    assert build_alan_hud(state, next_step="下一步：x").tone == "interference"
