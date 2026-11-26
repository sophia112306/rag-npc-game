"""主線換階段：把規格 v3 的四個階段對應到固定選項主線的劇情節點。"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.rules.scene_rules import SceneRules
from backend.schemas.game_state import GameState, StoryPhase


OPENING = ("meet_andre", "walk_to_council", "meet_vidalia", "ask_for_task")
TO_BORDER = (
    "travel_to_minglin_life_spring",
    "study_spring_ash",
    "enter_lieyi_plains",
    "observe_sacred_fire",
    "return_with_fire_findings",
    "travel_to_minglin_rune_grove",
    "trace_dust_runes",
    "enter_liuchen_valley",
    "listen_to_forgotten_names",
    "return_with_dust_findings",
)
TO_VETA = (
    "border_help_both",
    "return_after_border_choice",
    "enter_memory_library_with_map",
    "inspect_life_death_book",
    "inspect_invasion_archive",
    "contact_alan_observer",
    "seek_menmesvento_after_truths",
    "accept_dust_return_token",
    "return_to_minglin_for_veta",
    "enter_veta_source",
)


@pytest.mark.parametrize(
    ("current", "choice_id", "expected"),
    [
        (StoryPhase.ACT1_APPROACHING, "preview_border_ruins", StoryPhase.ACT2_MIDTERM),
        (StoryPhase.ACT2_MIDTERM, "enter_memory_library_alone", StoryPhase.ACT3_FREEDOM),
        (StoryPhase.ACT1_APPROACHING, "enter_veta_source", StoryPhase.ACT3_FREEDOM),
        (StoryPhase.ACT3_FREEDOM, "preview_border_ruins", StoryPhase.ACT3_FREEDOM),
        (StoryPhase.ACT2_MIDTERM, "observe_sacred_fire", StoryPhase.ACT2_MIDTERM),
        (StoryPhase.USURP_COUNTDOWN, "enter_memory_library_alone", StoryPhase.USURP_COUNTDOWN),
        (StoryPhase.ACT4_ENDING, "enter_veta_source", StoryPhase.ACT4_ENDING),
    ],
)
def test_phase_only_moves_forward_at_mapped_choices(current, choice_id, expected) -> None:
    state = GameState(session_id="phase-unit", story_phase=current)

    assert SceneRules.phase_after_story_choice(state, choice_id) == expected


def test_entering_a_phase_resets_phase_turns_and_dialogue_counters() -> None:
    state = GameState(
        session_id="phase-unit",
        phase_turns=12,
        phase_usurp_dialogue_gain=10,
        phase_relation_dialogue_gain={"andre": 40, "vidalia": 15, "menmesvento": 0},
    )

    changed = SceneRules.enter_phase(state, StoryPhase.ACT2_MIDTERM)

    assert changed is True
    assert state.story_phase == StoryPhase.ACT2_MIDTERM
    assert state.phase_turns == 0
    assert state.phase_usurp_dialogue_gain == 0
    assert state.phase_relation_dialogue_gain == {"andre": 0, "vidalia": 0, "menmesvento": 0}
    assert state.dialogue_counters_phase == StoryPhase.ACT2_MIDTERM
    assert SceneRules.enter_phase(state, StoryPhase.ACT2_MIDTERM) is False


def test_dialogue_after_phase_change_uses_the_new_phase_cap() -> None:
    from backend.rules.state_rules import StateRules

    state = GameState(session_id="phase-unit", axis=-20)
    SceneRules.enter_phase(state, StoryPhase.ACT2_MIDTERM)

    applied = StateRules.apply_dialogue_delta(state, axis_delta=-5, player_message="我想留在這裡")

    assert applied.axis == -5
    assert state.axis == -25


def _submit(client: TestClient, session_id: str, choice_id: str) -> dict:
    state = client.get(f"/api/game/{session_id}/state").json()
    choices = client.get(f"/api/game/{session_id}/choices").json()
    choice = next(choice for choice in choices if choice["choice_id"] == choice_id)
    response = client.post(
        "/api/game/turn",
        json={
            "session_id": session_id,
            "action_id": str(uuid4()),
            "message": choice["message"],
            "input_type": "text",
            "target_npc_id": choice["target_npc_id"],
            "action_mode": choice["action_mode"],
            "destination_scene_id": choice["destination_scene_id"],
            "story_choice_id": choice["choice_id"],
            "expected_state_version": state["state_version"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_main_story_moves_through_three_phases(tmp_path) -> None:
    app = create_app(f"sqlite+aiosqlite:///{tmp_path / 'phases.db'}")
    session_id = "phase-flow"

    def phase() -> StoryPhase:
        state = client.portal.call(app.state.game_orchestrator.get_state, session_id)
        return state.story_phase

    with TestClient(app) as client:
        assert client.post("/api/game/start", json={"session_id": session_id}).status_code == 201
        for choice_id in OPENING + TO_BORDER:
            _submit(client, session_id, choice_id)
        assert phase() == StoryPhase.ACT1_APPROACHING

        _submit(client, session_id, "preview_border_ruins")
        assert phase() == StoryPhase.ACT2_MIDTERM

        for choice_id in TO_VETA:
            _submit(client, session_id, choice_id)
            if choice_id == "enter_memory_library_with_map":
                assert phase() == StoryPhase.ACT3_FREEDOM
                state = client.portal.call(app.state.game_orchestrator.get_state, session_id)
                assert state.phase_turns == 1
        assert phase() == StoryPhase.ACT3_FREEDOM
