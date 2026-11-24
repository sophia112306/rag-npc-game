"""規格 v3：敘事 AI 提出的對話數值，必須經過程式的上限、封頂與防刷分。"""

from backend.rules.state_rules import StateRules, normalize_dialogue_message
from backend.schemas.game_state import GameState, StoryPhase


def make_state(**overrides) -> GameState:
    return GameState(session_id="dialogue-rules", **overrides)


def test_per_turn_limits_clamp_ai_proposal() -> None:
    state = make_state(story_phase=StoryPhase.ACT3_FREEDOM)

    result = StateRules.apply_dialogue_delta(
        state,
        axis_delta=9,
        usurp_delta=7,
        relation_deltas={"andre": 25, "vidalia": -30},
        player_message="我們一起去調查裂隙吧",
    )

    assert result.axis == 5
    assert result.usurp == 2
    assert result.relation == {"andre": 10, "vidalia": -10}
    assert state.axis == 5
    assert state.usurp == 2
    assert state.npc_states["andre"].relation == 30
    assert state.npc_states["vidalia"].relation == 20


def test_dialogue_never_lowers_usurp() -> None:
    state = make_state(story_phase=StoryPhase.ACT3_FREEDOM, usurp=40)

    result = StateRules.apply_dialogue_delta(state, usurp_delta=-5, player_message="我不會再幫外面的人了")

    assert result.usurp == 0
    assert state.usurp == 40


def test_only_three_spec_relations_are_accepted() -> None:
    state = make_state()

    result = StateRules.apply_dialogue_delta(
        state,
        relation_deltas={"seth": 10, "ghost": 10, "menmesvento": 4},
        player_message="死亡讓生命有重量",
    )

    assert result.relation == {"menmesvento": 4}
    assert state.npc_states["seth"].relation == 30
    assert "ghost" not in state.npc_states


def test_relation_dialogue_gain_is_capped_at_40_per_phase() -> None:
    state = make_state(
        dialogue_counters_phase=StoryPhase.ACT1_APPROACHING,
        phase_relation_dialogue_gain={"andre": 35, "vidalia": 0, "menmesvento": 0},
    )

    result = StateRules.apply_dialogue_delta(state, relation_deltas={"andre": 10}, player_message="這道裂隙通往哪裡")

    assert result.relation == {"andre": 5}
    assert state.phase_relation_dialogue_gain["andre"] == 40


def test_relation_loss_is_not_limited_by_phase_gain() -> None:
    state = make_state(
        dialogue_counters_phase=StoryPhase.ACT1_APPROACHING,
        phase_relation_dialogue_gain={"andre": 40, "vidalia": 0, "menmesvento": 0},
    )

    result = StateRules.apply_dialogue_delta(state, relation_deltas={"andre": -6}, player_message="你們都只是幻影")

    assert result.relation == {"andre": -6}


def test_usurp_from_provoking_npcs_is_capped_at_10_per_phase() -> None:
    state = make_state(
        story_phase=StoryPhase.ACT3_FREEDOM,
        dialogue_counters_phase=StoryPhase.ACT3_FREEDOM,
        phase_usurp_dialogue_gain=9,
    )

    first = StateRules.apply_dialogue_delta(state, usurp_delta=2, player_message="快把泉水交出來")
    second = StateRules.apply_dialogue_delta(state, usurp_delta=2, player_message="不交我就毀掉這裡")

    assert first.usurp == 1
    assert second.usurp == 0
    assert state.phase_usurp_dialogue_gain == 10


def test_same_sentence_counts_once_within_three_turns() -> None:
    state = make_state()

    first = StateRules.apply_dialogue_delta(state, relation_deltas={"vidalia": 5}, player_message="我會陪著妳。")
    repeat = StateRules.apply_dialogue_delta(state, relation_deltas={"vidalia": 5}, player_message="我會陪著妳！")

    assert first.relation == {"vidalia": 5}
    assert repeat.duplicate_message is True
    assert repeat.changed is False
    assert state.npc_states["vidalia"].relation == 35


def test_same_sentence_counts_again_after_three_other_turns() -> None:
    state = make_state()
    StateRules.apply_dialogue_delta(state, relation_deltas={"vidalia": 5}, player_message="我會陪著妳")
    for message in ("鳴霖的雨很美", "妳去過哪些地方", "外面的世界很吵"):
        StateRules.apply_dialogue_delta(state, player_message=message)

    again = StateRules.apply_dialogue_delta(state, relation_deltas={"vidalia": 5}, player_message="我會陪著妳")

    assert again.duplicate_message is False
    assert again.relation == {"vidalia": 5}


def test_same_stance_on_axis_counts_once_within_three_turns() -> None:
    state = make_state(story_phase=StoryPhase.ACT3_FREEDOM)

    first = StateRules.apply_dialogue_delta(state, axis_delta=4, player_message="死亡讓生命有意義")
    second = StateRules.apply_dialogue_delta(state, axis_delta=4, player_message="我們應該打破循環")

    assert first.axis == 4
    assert second.axis == 0


def test_phase_caps_still_apply_to_dialogue() -> None:
    state = make_state(axis=-18)

    result = StateRules.apply_dialogue_delta(state, axis_delta=-5, player_message="我想永遠留在這裡")

    assert result.axis == -2
    assert state.axis == -20


def test_counters_reset_when_phase_changes() -> None:
    state = make_state(
        story_phase=StoryPhase.ACT2_MIDTERM,
        dialogue_counters_phase=StoryPhase.ACT1_APPROACHING,
        phase_usurp_dialogue_gain=10,
        phase_relation_dialogue_gain={"andre": 40, "vidalia": 40, "menmesvento": 40},
    )

    result = StateRules.apply_dialogue_delta(
        state, usurp_delta=2, relation_deltas={"andre": 10}, player_message="長老會在抽泉水"
    )

    assert result.usurp == 2
    assert result.relation == {"andre": 10}
    assert state.dialogue_counters_phase == StoryPhase.ACT2_MIDTERM
    assert state.phase_relation_dialogue_gain == {"andre": 10, "vidalia": 0, "menmesvento": 0}


def test_normalize_ignores_spacing_and_punctuation() -> None:
    assert normalize_dialogue_message(" 我會陪著妳！ ") == normalize_dialogue_message("我會陪著妳。")
