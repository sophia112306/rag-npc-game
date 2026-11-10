"""Authorization tests for NPC knowledge and memory context."""

import pytest
import pytest_asyncio

from backend.content.characters import CHARACTER_DEFINITIONS
from backend.content.context_repository import CharacterDefinitionNotFoundError, NPCContextRepository
from backend.database import create_async_session_factory, create_database_engine, create_schema
from backend.database.repository import SqlAlchemyGameRepository
from backend.schemas.content import DisclosureScope, KnowledgeRecordInput, MemoryRecordInput
from backend.schemas.game_state import GameState
from backend.schemas.progression import (
    CommitmentRecordInput,
    CommitmentStatus,
    GoalStatus,
    NPCGoalRecordInput,
    ProgressionSourceKind,
)


@pytest_asyncio.fixture
async def context_repository(tmp_path):
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'context.db'}")
    await create_schema(engine)
    session_factory = create_async_session_factory(engine)
    game_repository = SqlAlchemyGameRepository(session_factory)
    await game_repository.create_or_get_session(GameState(session_id="context-session"))
    repository = NPCContextRepository(session_factory)
    await repository.ensure_character_definition(CHARACTER_DEFINITIONS["vidalia"])
    yield repository
    await engine.dispose()


@pytest.mark.asyncio
async def test_context_only_contains_authorized_npc_knowledge(context_repository) -> None:
    repository = context_repository
    await repository.add_knowledge(
        KnowledgeRecordInput(
            session_id="context-session",
            knower_npc_id="vidalia",
            subject_key="observed_player_greeting",
            content="玩家曾向維達利亞問候。",
            epistemic_status="known",
            source_kind="action",
            source_id="action-visible",
            acquired_turn=1,
            available_from_turn=1,
            is_unlocked=True,
            disclosure_scope=DisclosureScope.CONDITIONAL,
            provenance={"test": "visible"},
        )
    )
    await repository.add_knowledge(
        KnowledgeRecordInput(
            session_id="context-session",
            knower_npc_id="vidalia",
            subject_key="locked_secret",
            content="尚未解鎖的秘密。",
            epistemic_status="known",
            source_kind="canon",
            source_id="secret-canon",
            acquired_turn=0,
            available_from_turn=0,
            is_unlocked=False,
            provenance={"test": "locked"},
        )
    )
    await repository.add_knowledge(
        KnowledgeRecordInput(
            session_id="context-session",
            knower_npc_id="andre",
            subject_key="andre_only",
            content="只有安德烈知道的內容。",
            epistemic_status="known",
            source_kind="event",
            source_id="andre-event",
            acquired_turn=1,
            available_from_turn=1,
            is_unlocked=True,
            provenance={"test": "other_npc"},
        )
    )
    await repository.add_knowledge(
        KnowledgeRecordInput(
            session_id="context-session",
            knower_npc_id="vidalia",
            subject_key="future_knowledge",
            content="未來回合才能使用。",
            epistemic_status="hearsay",
            source_kind="event",
            source_id="future-event",
            acquired_turn=3,
            available_from_turn=3,
            is_unlocked=True,
            provenance={"test": "future"},
        )
    )

    context = await repository.get_generation_context("context-session", "vidalia", 1)

    assert [item.subject_key for item in context.knowledge] == ["observed_player_greeting"]
    assert "character_definition_incomplete" in context.missing_data
    assert "private_character_profile_missing" in context.missing_data


@pytest.mark.asyncio
async def test_context_only_contains_active_memories_for_the_target_npc(context_repository) -> None:
    repository = context_repository
    await repository.add_memory(
        MemoryRecordInput(
            session_id="context-session",
            npc_id="vidalia",
            content="維達利亞親眼看見玩家抵達。",
            memory_type="observed",
            occurred_turn=1,
            importance=20,
            provenance={"test": "active"},
        )
    )
    await repository.add_memory(
        MemoryRecordInput(
            session_id="context-session",
            npc_id="vidalia",
            content="已失效的摘要。",
            memory_type="summary",
            occurred_turn=1,
            is_active=False,
            provenance={"test": "inactive"},
        )
    )
    await repository.add_memory(
        MemoryRecordInput(
            session_id="context-session",
            npc_id="andre",
            content="安德烈的私人記憶。",
            memory_type="observed",
            occurred_turn=1,
            provenance={"test": "other_npc"},
        )
    )

    context = await repository.get_generation_context("context-session", "vidalia", 1)

    assert [item.content for item in context.memories] == ["維達利亞親眼看見玩家抵達。"]


@pytest.mark.asyncio
async def test_unregistered_character_cannot_receive_generation_context(context_repository) -> None:
    with pytest.raises(CharacterDefinitionNotFoundError):
        await context_repository.get_generation_context("context-session", "unknown", 1)


@pytest.mark.asyncio
async def test_turn_context_limits_goals_to_due_active_target_records(context_repository) -> None:
    repository = context_repository
    for item in (
        NPCGoalRecordInput(
            session_id="context-session",
            npc_id="vidalia",
            summary="目前應重新檢視的高優先目標。",
            priority=90,
            created_turn=0,
            next_review_turn=1,
            source_kind=ProgressionSourceKind.AUTHOR,
            source_id="team-goal-1",
        ),
        NPCGoalRecordInput(
            session_id="context-session",
            npc_id="vidalia",
            summary="未來回合才檢視。",
            priority=100,
            created_turn=0,
            next_review_turn=5,
            source_kind=ProgressionSourceKind.AUTHOR,
            source_id="team-goal-future",
        ),
        NPCGoalRecordInput(
            session_id="context-session",
            npc_id="vidalia",
            summary="已完成的舊目標。",
            priority=100,
            status=GoalStatus.COMPLETED,
            created_turn=0,
            next_review_turn=0,
            source_kind=ProgressionSourceKind.ESTABLISHED_EVENT,
            source_id="event-completed-goal",
        ),
        NPCGoalRecordInput(
            session_id="context-session",
            npc_id="andre",
            summary="其他 NPC 的目標。",
            priority=100,
            created_turn=0,
            next_review_turn=0,
            source_kind=ProgressionSourceKind.AUTHOR,
            source_id="andre-goal",
        ),
    ):
        await repository.add_goal(item)

    context = await repository.get_generation_context("context-session", "vidalia", 1)

    assert [goal.summary for goal in context.active_goals] == ["目前應重新檢視的高優先目標。"]


@pytest.mark.asyncio
async def test_turn_context_only_includes_active_commitments_for_target_npc(context_repository) -> None:
    repository = context_repository
    for item in (
        CommitmentRecordInput(
            session_id="context-session",
            summary="玩家答應下回合帶回線索。",
            promisor_id="context-session-player",
            promisee_id="vidalia",
            created_turn=1,
            due_turn=2,
            source_kind=ProgressionSourceKind.ESTABLISHED_EVENT,
            source_id="event-visible-promise",
        ),
        CommitmentRecordInput(
            session_id="context-session",
            summary="已履行的承諾。",
            promisor_id="vidalia",
            promisee_id="context-session-player",
            status=CommitmentStatus.FULFILLED,
            created_turn=0,
            source_kind=ProgressionSourceKind.ESTABLISHED_EVENT,
            source_id="event-fulfilled-promise",
        ),
        CommitmentRecordInput(
            session_id="context-session",
            summary="與目標 NPC 無關的承諾。",
            promisor_id="andre",
            promisee_id="menmesvento",
            created_turn=1,
            source_kind=ProgressionSourceKind.ESTABLISHED_EVENT,
            source_id="event-other-promise",
        ),
    ):
        await repository.add_commitment(item)

    context = await repository.get_generation_context("context-session", "vidalia", 2)

    assert [item.summary for item in context.active_commitments] == [
        "玩家答應下回合帶回線索。"
    ]
