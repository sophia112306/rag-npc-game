"""終局維塔三問與五個結局（規格 v3「結局判定與終局對話」）。

第 1、2 題只記入尾聲旗標、不加數值；可選結局完全由進入終局時的主軸、
真相度、關係值與旗標決定。新夢、塵歸要靠對話累積的數值，固定選項路線走不到，
所以在這裡用指定狀態驗證。
"""

from uuid import uuid4

import pytest

from backend.content.demo_story import available_demo_story_choices
from backend.database import create_async_session_factory, create_database_engine, create_schema
from backend.database.repository import SqlAlchemyGameRepository
from backend.generation.rule_based_planner import RuleBasedStoryPlanner
from backend.orchestration.game_orchestrator import GameOrchestrator
from backend.schemas.game_state import GameState, PlayerState, StoryPhase
from backend.schemas.player_action import PlayerAction


def veta_state(relations=None, axis=0, **flags) -> GameState:
    state = GameState(
        session_id="veta-endings",
        current_scene_id="minglin",
        player=PlayerState(player_id="player"),
        story_phase=StoryPhase.ACT3_FREEDOM,
        truth_level=3,
        axis=axis,
    )
    state.story_progress.node_id = "veta_route_ready"
    state.story_progress.completed_choice_ids = ["border_help_both", "contact_alan_observer"]
    state.story_progress.unlocked_scene_ids += ["lieyi_plains", "liuchen_valley", "memory_library"]
    state.flags.update(flags)
    for npc_id, relation in (relations or {}).items():
        state.npc_states[npc_id].relation = relation
    return state


async def _play(tmp_path, state: GameState, *choice_ids: str) -> GameState:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'veta.db'}")
    await create_schema(engine)
    repository = SqlAlchemyGameRepository(create_async_session_factory(engine))
    await repository.create_or_get_session(state)
    orchestrator = GameOrchestrator(repository, story_planner=RuleBasedStoryPlanner(None))
    for choice_id in choice_ids:
        current = await repository.get_state(state.session_id)
        choice = next(c for c in await orchestrator.get_player_choices(state.session_id) if c.choice_id == choice_id)
        await orchestrator.process_turn(PlayerAction(
            session_id=state.session_id,
            action_id=uuid4(),
            message=choice.message,
            action_mode=choice.action_mode,
            target_npc_id=choice.target_npc_id,
            destination_scene_id=choice.destination_scene_id,
            story_choice_id=choice.choice_id,
            expected_state_version=current.state_version,
        ))
    return await repository.get_state(state.session_id)


_TO_FINAL_CHOICE = ("enter_veta_source", "veta_q1_each_life", "veta_q2_release")


def final_choices(state: GameState) -> set[str]:
    return {
        choice.choice_id
        for choice in available_demo_story_choices(state)
        if choice.choice_id.startswith("choose_")
    }


@pytest.mark.asyncio
async def test_first_two_questions_only_record_epilogue_flags(tmp_path) -> None:
    state = veta_state(relations={"vidalia": 50, "menmesvento": 50}, axis=5)

    stored = await _play(tmp_path, state, *_TO_FINAL_CHOICE)

    assert stored.story_progress.node_id == "veta_final_choice"
    assert stored.axis == 5
    assert stored.usurp == 0
    assert stored.npc_states["vidalia"].relation == 50
    assert stored.npc_states["menmesvento"].relation == 50
    assert set(stored.flags["epilogue_flags"]) == {"answer_q1", "answer_q2"}


@pytest.mark.parametrize(
    ("relations", "axis", "flags", "expected", "chosen", "ending"),
    [
        # 中間區：長眠、醒來（門梅司文托 ≥ 40）、新夢（雙 60、真相 3、未轉化）
        (
            {"vidalia": 60, "menmesvento": 60}, 0, {},
            {"choose_long_sleep", "choose_wake", "choose_new_dream"}, "choose_new_dream", "新夢",
        ),
        # 守夢區：長眠，持有塵歸令再加塵歸
        (
            {}, -25, {"has_dust_token": True},
            {"choose_long_sleep", "choose_dust_return"}, "choose_dust_return", "塵歸",
        ),
        # 醒夢區：醒來（門梅司文托 ≥ 40）
        ({"menmesvento": 40}, 25, {}, {"choose_wake"}, "choose_wake", "醒來"),
        # 醒夢區但門梅司文托不到 40：醒來退回長眠
        ({"menmesvento": 39}, 25, {}, {"choose_long_sleep"}, "choose_long_sleep", "長眠"),
    ],
)
@pytest.mark.asyncio
async def test_final_choice_follows_values_at_entry(
    tmp_path, relations, axis, flags, expected, chosen, ending
) -> None:
    state = veta_state(relations=relations, axis=axis, **flags)

    at_choice = await _play(tmp_path, state, *_TO_FINAL_CHOICE)
    assert final_choices(at_choice) == expected

    stored = await _play(tmp_path, at_choice, chosen)
    assert stored.game_status == "completed"
    assert stored.final_ending == ending


@pytest.mark.asyncio
async def test_transformed_player_loses_new_dream_and_dust_return(tmp_path) -> None:
    state = veta_state(
        relations={"vidalia": 70, "menmesvento": 70}, axis=0, has_dust_token=True, is_transformed=True
    )

    at_choice = await _play(tmp_path, state, *_TO_FINAL_CHOICE)

    assert final_choices(at_choice) == {"choose_long_sleep", "choose_wake"}
