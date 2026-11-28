"""階段三事件：E3-2、E3-3、E3-4、真相 C 後拒絕艾倫、拆除符印（規格 v3 事件清單）。"""

from uuid import uuid4

import pytest

from backend.content.demo_story import available_demo_story_choices
from backend.database import create_async_session_factory, create_database_engine, create_schema
from backend.database.repository import SqlAlchemyGameRepository
from backend.generation.rule_based_planner import RuleBasedStoryPlanner
from backend.orchestration.game_orchestrator import GameOrchestrator
from backend.rules.ending_rules import EndingRules
from backend.schemas.game_state import GameState, PlayerState, StoryPhase
from backend.schemas.player_action import PlayerAction


def act3_state(node_id="veta_route_ready", scene_id="minglin", relations=None, axis=0, **flags) -> GameState:
    state = GameState(
        session_id="act3",
        current_scene_id=scene_id,
        player=PlayerState(player_id="player"),
        story_phase=StoryPhase.ACT3_FREEDOM,
        truth_level=3,
        axis=axis,
    )
    state.story_progress.node_id = node_id
    state.story_progress.completed_choice_ids = ["border_help_both", "contact_alan_observer"]
    state.story_progress.unlocked_scene_ids += ["lieyi_plains", "liuchen_valley", "memory_library"]
    state.flags.update({"truth_c_unlocked": True, **flags})
    for npc_id, relation in (relations or {}).items():
        state.npc_states[npc_id].relation = relation
    return state


def ids(state: GameState) -> list[str]:
    return [choice.choice_id for choice in available_demo_story_choices(state)]


def test_hub_without_relations_offers_stance_and_veta_source() -> None:
    assert ids(act3_state()) == [
        "affirm_preserve_cycle", "affirm_accept_endings", "enter_veta_source"
    ]


def test_concurrent_hub_events_all_remain_available() -> None:
    state = act3_state(
        relations={"vidalia": 60, "andre": 60},
        placed_runes=["lieyi_plains"],
    )

    assert ids(state) == [
        "affirm_preserve_cycle", "affirm_accept_endings", "enter_veta_source",
        "vidalia_asks_outside", "andre_shows_breach", "remove_placed_runes",
    ]

    state.story_progress.completed_choice_ids.append("affirm_preserve_cycle")
    assert ids(state) == [
        "enter_veta_source", "vidalia_asks_outside", "andre_shows_breach",
        "remove_placed_runes",
    ]


@pytest.mark.asyncio
async def test_concurrent_hub_events_can_all_resolve_before_veta(tmp_path) -> None:
    state = act3_state(
        relations={"vidalia": 70, "andre": 70},
        placed_runes=["lieyi_plains"],
        has_dust_token=True,
    )

    stored = await _play(
        tmp_path, state, "affirm_preserve_cycle", "vidalia_offer_weaving",
        "decline_dream_weaving", "andre_shows_breach", "remove_placed_runes",
        "enter_veta_source", "veta_q1_each_life", "veta_q2_release",
        "choose_dust_return",
    )

    assert stored.final_ending == "塵歸"
    assert stored.flags["hidden_cave_unlocked"] is True
    assert stored.flags["placed_runes"] == []
    assert stored.flags["is_transformed"] is False


@pytest.mark.parametrize(
    ("axis", "expected"),
    [(-20, "vidalia_offer_weaving"), (20, "vidalia_confides_wavering"), (0, "vidalia_asks_outside"), (-19, "vidalia_asks_outside")],
)
def test_vidalia_heart_event_follows_axis(axis, expected) -> None:
    state = act3_state(relations={"vidalia": 60}, axis=axis)

    vidalia_events = [choice_id for choice_id in ids(state) if choice_id.startswith("vidalia_")]

    assert vidalia_events == [expected]


def test_vidalia_heart_event_needs_relation_60_and_happens_once() -> None:
    assert not any(choice_id.startswith("vidalia_") for choice_id in ids(act3_state(relations={"vidalia": 59})))

    done = act3_state(relations={"vidalia": 70}, axis=0)
    done.story_progress.completed_choice_ids.append("vidalia_offer_weaving")
    assert not any(choice_id.startswith("vidalia_") for choice_id in ids(done))


def test_andre_evidence_and_menmesvento_request_need_relation_60() -> None:
    assert "andre_shows_breach" in ids(act3_state(relations={"andre": 60}))
    assert "andre_shows_breach" not in ids(act3_state(relations={"andre": 59}))

    offer = act3_state("dust_token_decided", "liuchen_valley", relations={"menmesvento": 60})
    assert ids(offer) == ["return_to_minglin_for_veta", "agree_wake_veta", "refuse_wake_veta"]
    offer.story_progress.completed_choice_ids.append("refuse_wake_veta")
    assert ids(offer) == ["return_to_minglin_for_veta"]


def test_rune_removal_needs_placed_runes_and_warning_or_truth_c() -> None:
    assert "remove_placed_runes" in ids(act3_state(placed_runes=["lieyi_plains"]))
    assert "remove_placed_runes" not in ids(act3_state(placed_runes=[]))
    assert "remove_placed_runes" not in ids(act3_state(placed_runes=["lieyi_plains"], truth_c_unlocked=False))


async def _play(tmp_path, state: GameState, *choice_ids: str) -> GameState:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'act3.db'}")
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


@pytest.mark.asyncio
async def test_accepting_dream_weaving_transforms_the_player_and_closes_endings(tmp_path) -> None:
    state = act3_state(relations={"vidalia": 70, "menmesvento": 70}, axis=-25, has_dust_token=True)

    stored = await _play(tmp_path, state, "vidalia_offer_weaving", "accept_dream_weaving")

    assert stored.flags["is_transformed"] is True
    assert stored.flags["transformed_race"] == "elf"
    assert stored.axis == -45
    assert stored.npc_states["vidalia"].relation == 70  # 規格：接受織夢不加關係值
    assert stored.story_progress.node_id == "veta_route_ready"
    endings = EndingRules.evaluate_available_endings(stored)
    assert "新夢" not in endings and "塵歸" not in endings


@pytest.mark.asyncio
async def test_declining_dream_weaving_changes_nothing(tmp_path) -> None:
    state = act3_state(relations={"vidalia": 70}, axis=-25)

    stored = await _play(tmp_path, state, "vidalia_offer_weaving", "decline_dream_weaving")

    assert stored.flags["is_transformed"] is False
    assert stored.axis == -25
    assert "vidalia_offer_weaving" not in ids(stored)


@pytest.mark.asyncio
async def test_removing_runes_lowers_usurp_per_site(tmp_path) -> None:
    state = act3_state(placed_runes=["minglin_life_spring", "lieyi_plains"])
    state.usurp = 40

    stored = await _play(tmp_path, state, "remove_placed_runes")

    assert stored.usurp == 20
    assert stored.flags["placed_runes"] == []
    assert "remove_placed_runes" not in ids(stored)


@pytest.mark.asyncio
async def test_andre_evidence_unlocks_the_hidden_cave_without_values(tmp_path) -> None:
    state = act3_state(relations={"andre": 60})

    stored = await _play(tmp_path, state, "andre_shows_breach")

    assert stored.flags["hidden_cave_unlocked"] is True
    assert stored.npc_states["andre"].relation == 60  # 規格：E3-4 無數值
    assert "andre_shows_breach" not in ids(stored)


@pytest.mark.asyncio
async def test_agreeing_to_wake_veta_applies_e3_2(tmp_path) -> None:
    state = act3_state("dust_token_decided", "liuchen_valley", relations={"menmesvento": 60})

    stored = await _play(tmp_path, state, "agree_wake_veta")

    assert stored.axis == 10
    assert stored.npc_states["menmesvento"].relation == 70
    assert stored.story_progress.node_id == "dust_token_decided"
