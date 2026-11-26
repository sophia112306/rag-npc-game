from backend.content.alan_hud import build_alan_hud
from backend.schemas.game_state import GameState, StoryPhase
from backend.schemas.player_view import project_player_view


def test_alan_stays_calm_at_the_start_and_is_player_view_data() -> None:
    state = GameState(session_id="alan-start", current_scene_id="minglin")

    hud = build_alan_hud(state)
    view = project_player_view(state)

    assert hud.tone == "calm"
    assert hud.display_value == 0
    assert hud.label == "視網膜連線"
    assert view.alan_hud == hud


def test_alan_warns_at_existing_usurp_boundaries() -> None:
    urgent = GameState(session_id="alan-urgent", current_scene_id="minglin", usurp=50)
    warning = GameState(
        session_id="alan-warning",
        current_scene_id="minglin",
        usurp=75,
        warning_triggered=True,
    )

    assert build_alan_hud(urgent).tone == "urgent"
    assert build_alan_hud(warning).tone == "interference"
    assert build_alan_hud(warning).persistent is True


def test_alan_reports_override_countdown_without_exposing_private_state() -> None:
    state = GameState(
        session_id="alan-override",
        current_scene_id="minglin",
        usurp=90,
        story_phase=StoryPhase.USURP_COUNTDOWN,
        usurp_countdown_turns=2,
        truth_level=2,
    )

    hud = build_alan_hud(state)

    assert hud.tone == "override"
    assert hud.countdown_turns == 2
    assert hud.label == "艾倫連線"
    assert "篡奪率" not in hud.message
    assert "world" not in hud.model_dump()
