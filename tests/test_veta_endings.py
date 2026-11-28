"""終局維塔三問與五個結局（規格 v3「結局判定與終局對話」）。

第 1、2 題只記入尾聲旗標、不加數值；可選結局完全由進入終局時的主軸、
真相度、關係值與旗標決定。新夢要靠對話累積的關係值；一般主軸路線的塵歸
也要累積主軸。進入維塔源頭前的固定立場選項提供離線路線。
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
from backend.schemas.api_response import DeltaPayload, NarrativeAIResponse
from backend.schemas.story import DialogueLine, SpeakerType, StoryProposal


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


@pytest.mark.asyncio
async def test_offline_fixed_choices_can_reach_dust_return_during_usurp_countdown(tmp_path) -> None:
    state = veta_state(has_dust_token=True)

    at_choice = await _play(
        tmp_path, state, "enter_veta_source", "veta_q1_recurring_life",
        "veta_q2_control", "confirm_usurp_after_warning",
    )

    assert at_choice.usurp >= 90
    assert "choose_dust_return" in final_choices(at_choice)
    stored = await _play(tmp_path, at_choice, "choose_dust_return")
    assert stored.final_ending == "塵歸"


@pytest.mark.asyncio
async def test_new_dream_is_reachable_by_bounded_dialogue_relationship_gains(tmp_path) -> None:
    class AffinityJudge:
        async def judge(self, request):
            return NarrativeAIResponse(
                scene=request.scene_name,
                speaker=request.target_npc_id,
                delta=DeltaPayload(relation={request.target_npc_id: 10}),
                reason="對話增進信任",
            )

    class PassivePlanner:
        async def propose(self, action, parsed_action, state, turn_guidance):
            npc = state.npc_states[action.target_npc_id]
            return StoryProposal(
                session_id=action.session_id,
                turn_number=state.turn_count + 1,
                intent_summary="NPC 回應玩家。",
                proposed_dialogue=[DialogueLine(
                    speaker_type=SpeakerType.NPC,
                    speaker_id=action.target_npc_id,
                    speaker_name=npc.name,
                    text="我聽見你的想法。",
                )],
            )

    state = veta_state(relations={"menmesvento": 40, "vidalia": 30}, has_dust_token=True)
    state.current_scene_id = "liuchen_valley"
    state.story_progress.node_id = "dust_token_decided"
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'new-dream.db'}")
    await create_schema(engine)
    repository = SqlAlchemyGameRepository(create_async_session_factory(engine))
    await repository.create_or_get_session(state)
    orchestrator = GameOrchestrator(
        repository, story_planner=PassivePlanner(), narrative_judge=AffinityJudge()
    )

    async def talk_to(npc_id: str, message: str) -> None:
        current = await repository.get_state(state.session_id)
        await orchestrator.process_turn(PlayerAction(
            session_id=state.session_id,
            action_id=uuid4(),
            message=message,
            target_npc_id=npc_id,
            expected_state_version=current.state_version,
        ))

    async def choose(choice_id: str) -> None:
        current = await repository.get_state(state.session_id)
        choice = next(
            choice for choice in await orchestrator.get_player_choices(state.session_id)
            if choice.choice_id == choice_id
        )
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

    for message in (
        "我想了解你記下的那些名字。",
        "謝謝你告訴我他們的故事。",
        "我想知道這段記憶對你意味著什麼。",
        "你願意再說說他們的願望嗎？",
    ):
        await talk_to("menmesvento", message)
    await choose("return_to_minglin_for_veta")
    for message in (
        "我想聽聽妳以前走過哪些地方。",
        "那些旅行之後，妳最懷念什麼？",
        "謝謝妳願意和我分享回憶。",
        "妳第一次看見這座森林時是什麼感覺？",
        "我們可以再聊聊妳走過的地方嗎？",
    ):
        await talk_to("vidalia", message)
    for choice_id in _TO_FINAL_CHOICE:
        await choose(choice_id)

    at_choice = await repository.get_state(state.session_id)
    assert at_choice.axis == 0
    assert at_choice.npc_states["menmesvento"].relation == 64
    assert at_choice.npc_states["vidalia"].relation == 60
    assert "choose_new_dream" in final_choices(at_choice)
    await choose("choose_new_dream")
    stored = await repository.get_state(state.session_id)
    assert stored.final_ending == "新夢"
    await engine.dispose()
