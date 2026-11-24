"""階段二選做支線（E2-1 抽泉裝置、E2-4 觀測符印）與警告事件 W。"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from backend.content.demo_story import (
    SIDE_EVENT_ENTRY_IDS,
    available_demo_story_choices,
    pending_warning_choices,
)
from backend.database import create_async_session_factory, create_database_engine, create_schema
from backend.database.repository import SqlAlchemyGameRepository
from backend.generation.rule_based_planner import RuleBasedStoryPlanner
from backend.main import create_app
from backend.orchestration.game_orchestrator import GameOrchestrator
from backend.schemas.game_state import GameState, PlayerState, StoryPhase
from backend.schemas.player_action import PlayerAction
from test_demo_story_flow import _start, _submit_choice


TO_BORDER = (
    "travel_to_minglin_life_spring", "study_spring_ash", "enter_lieyi_plains",
    "observe_sacred_fire", "return_with_fire_findings",
    "travel_to_minglin_rune_grove", "trace_dust_runes", "enter_liuchen_valley",
    "listen_to_forgotten_names", "return_with_dust_findings", "preview_border_ruins",
)


def _walk(client: TestClient, session_id: str, choice_ids) -> dict:
    state = _start(client, session_id)
    for choice_id in choice_ids:
        state = _submit_choice(client, session_id, state["state_version"], choice_id)["state"]
    return state


def _internal_state(client: TestClient, app, session_id: str) -> GameState:
    return client.portal.call(app.state.game_orchestrator.get_state, session_id)


def _choice_ids(client: TestClient, session_id: str) -> list[str]:
    return [choice["choice_id"] for choice in client.get(f"/api/game/{session_id}/choices").json()]


def test_side_trips_open_only_after_the_border_choice(tmp_path) -> None:
    app = create_app(f"sqlite+aiosqlite:///{tmp_path / 'side-open.db'}")
    with TestClient(app) as client:
        _walk(client, "side-open", TO_BORDER[:5])
        assert not SIDE_EVENT_ENTRY_IDS.intersection(_choice_ids(client, "side-open"))

        state = client.get("/api/game/side-open/state").json()
        for choice_id in (*TO_BORDER[5:], "border_ignore", "return_after_border_choice"):
            state = _submit_choice(client, "side-open", state["state_version"], choice_id)["state"]

        options = _choice_ids(client, "side-open")
        assert options[0] == "enter_memory_library_alone"
        assert set(options[1:]) == SIDE_EVENT_ENTRY_IDS
        assert "也可以先" in state["navigation"]["objective"]


def test_placing_all_three_runes_and_stopping_the_pump(tmp_path) -> None:
    app = create_app(f"sqlite+aiosqlite:///{tmp_path / 'side-place.db'}")
    with TestClient(app) as client:
        _walk(client, "side-place", (
            *TO_BORDER, "border_help_both", "return_after_border_choice",
            "side_spring_anomaly", "pump_prevent", "rune_place_spring",
            "side_fire_reactor", "rune_place_fire",
            "side_dust_fissure", "rune_place_dust",
        ))
        state = _internal_state(client, app, "side-place")

        assert state.story_phase == StoryPhase.ACT2_MIDTERM
        assert state.usurp == 45  # 抽泉 −5（夾在 0）＋符印 15 × 3
        assert state.npc_states["andre"].relation == 30  # E2-1 阻止：安德烈 +10
        assert state.flags["placed_runes"] == ["minglin_life_spring", "lieyi_plains", "liuchen_valley"]
        assert state.current_scene_id == "minglin"
        assert state.story_progress.node_id == "demo_complete"
        # 三處都去過之後只剩進圖書館的入口
        assert _choice_ids(client, "side-place") == ["enter_memory_library_with_map"]


def test_assisting_the_pump_marks_elder_cooperation_and_refusals_cost_nothing(tmp_path) -> None:
    app = create_app(f"sqlite+aiosqlite:///{tmp_path / 'side-assist.db'}")
    with TestClient(app) as client:
        _walk(client, "side-assist", (
            *TO_BORDER, "border_ignore", "return_after_border_choice",
            "side_spring_anomaly", "pump_assist", "rune_refuse_spring",
        ))
        state = _internal_state(client, app, "side-assist")

        assert state.usurp == 10
        assert state.flags["elder_cooperation"] is True
        assert state.flags["placed_runes"] == []
        assert "side_spring_anomaly" not in _choice_ids(client, "side-assist")


def _warning_state(**overrides) -> GameState:
    state = GameState(
        session_id="warning",
        current_scene_id="minglin",
        player=PlayerState(player_id="player"),
        story_phase=StoryPhase.ACT3_FREEDOM,
        usurp=75,
        warning_triggered=True,
        **overrides,
    )
    state.story_progress.node_id = "memory_truths_complete"
    state.story_progress.completed_choice_ids = ["border_help_both"]
    return state


def test_warning_event_is_forced_once_usurp_first_reaches_75() -> None:
    state = _warning_state()
    state.npc_states["vidalia"].relation = 65

    choices = available_demo_story_choices(state)

    assert [choice.choice_id for choice in choices] == ["warning_witness", "warning_expose_elders"]
    assert "維達利亞" in choices[0].response_text  # 關係值最高的 NPC 帶主角看異象
    assert all(choice.next_node_id == "memory_truths_complete" for choice in choices)


def test_warning_event_is_not_inserted_into_veta_or_repeated() -> None:
    veta = _warning_state()
    veta.story_progress.node_id = "veta_usurp_warning"
    assert pending_warning_choices(veta) == ()

    done = _warning_state()
    done.flags["warning_event_done"] = True
    assert pending_warning_choices(done) == ()


@pytest.mark.asyncio
async def test_exposing_the_elders_during_the_warning_lowers_usurp(tmp_path) -> None:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'warning.db'}")
    await create_schema(engine)
    session_factory = create_async_session_factory(engine)
    repository = SqlAlchemyGameRepository(session_factory)
    await repository.create_or_get_session(_warning_state())
    orchestrator = GameOrchestrator(repository, story_planner=RuleBasedStoryPlanner(None))
    choice = next(
        choice for choice in await orchestrator.get_player_choices("warning")
        if choice.choice_id == "warning_expose_elders"
    )

    await orchestrator.process_turn(PlayerAction(
        session_id="warning",
        action_id=uuid4(),
        message=choice.message,
        action_mode=choice.action_mode,
        target_npc_id=choice.target_npc_id,
        destination_scene_id=choice.destination_scene_id,
        story_choice_id=choice.choice_id,
        expected_state_version=1,
    ))

    stored = await repository.get_state("warning")
    assert stored.usurp == 65
    assert stored.flags["warning_event_done"] is True
    assert stored.story_progress.node_id == "memory_truths_complete"
    assert pending_warning_choices(stored) == ()
