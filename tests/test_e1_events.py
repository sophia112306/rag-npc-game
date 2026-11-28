"""規格 v3 階段一事件：E1-4「長老會的邀請」（首次進入烈燚原，選做、無數值）。"""

from uuid import uuid4

import pytest

from backend.content.demo_story import available_demo_story_choices
from backend.database import create_async_session_factory, create_database_engine, create_schema
from backend.database.repository import SqlAlchemyGameRepository
from backend.generation.rule_based_planner import RuleBasedStoryPlanner
from backend.orchestration.game_orchestrator import GameOrchestrator
from backend.schemas.game_state import GameState, PlayerState
from backend.schemas.player_action import PlayerAction


def lieyi_state() -> GameState:
    state = GameState(
        session_id="e1-4",
        current_scene_id="lieyi_plains",
        player=PlayerState(player_id="player"),
    )
    state.story_progress.node_id = "lieyi_arrival"
    state.story_progress.completed_choice_ids = ["enter_lieyi_plains"]
    state.story_progress.unlocked_scene_ids += ["lieyi_plains"]
    return state


def ids(state: GameState) -> list[str]:
    return [choice.choice_id for choice in available_demo_story_choices(state)]


async def _play(tmp_path, state: GameState, *choice_ids: str) -> GameState:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'e1.db'}")
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


def test_elder_invitation_is_offered_beside_the_fire_investigation() -> None:
    assert ids(lieyi_state()) == ["observe_sacred_fire", "question_fire_elder_motive", "hear_elder_invitation"]


@pytest.mark.asyncio
async def test_elder_invitation_records_a_flag_without_values_and_happens_once(tmp_path) -> None:
    state = lieyi_state()

    stored = await _play(tmp_path, state, "hear_elder_invitation")

    assert stored.flags["elder_invitation_heard"] is True
    assert stored.axis == 0
    assert stored.usurp == 0
    assert stored.npc_states["dasso"].relation == state.npc_states["dasso"].relation
    assert stored.story_progress.node_id == "lieyi_arrival"
    assert stored.npc_states["dasso"].met is True
    assert ids(stored) == ["observe_sacred_fire", "question_fire_elder_motive"]
