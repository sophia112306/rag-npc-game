"""Integration tests from untrusted story proposal through atomic persistence."""

from uuid import uuid4

from sqlalchemy import func, select

import pytest

from backend.database import create_async_session_factory, create_database_engine, create_schema
from backend.database.models import (
    ActionRecord,
    CommitmentRecord,
    GameEventRecord,
    MemoryRecord,
)
from backend.database.repository import SqlAlchemyGameRepository
from backend.orchestration.game_orchestrator import GameOrchestrator
from backend.schemas.game_state import GameState, PlayerState
from backend.schemas.player_action import PlayerAction
from backend.schemas.story import (
    EstablishCommitmentOperation,
    EventProposal,
    StoryProposal,
    TransferItemOperation,
)


class FixedPlanner:
    def __init__(self, item_id: str) -> None:
        self.item_id = item_id

    async def propose(self, action, parsed_action, state) -> StoryProposal:
        return StoryProposal(
            session_id=action.session_id,
            turn_number=state.turn_count + 1,
            intent_summary="Offer one proposed item transfer.",
            event_proposals=[
                EventProposal(
                    event_type="item_exchange",
                    description="Untrusted generated description.",
                    actor_id=state.player.player_id,
                    target_id="vidalia",
                    operations=[
                        TransferItemOperation(
                            item_id=self.item_id,
                            from_entity_id=state.player.player_id,
                            to_entity_id="vidalia",
                        )
                    ],
                    witness_ids=[state.player.player_id, "vidalia"],
                )
            ],
        )


class CommitmentPlanner:
    async def propose(self, action, parsed_action, state) -> StoryProposal:
        return StoryProposal(
            session_id=action.session_id,
            turn_number=state.turn_count + 1,
            intent_summary="Create one explicit commitment.",
            event_proposals=[
                EventProposal(
                    event_type="commitment_created",
                    description="Untrusted generated wording.",
                    actor_id=state.player.player_id,
                    target_id="vidalia",
                    operations=[
                        EstablishCommitmentOperation(
                            summary="玩家答應在三回合內帶回地圖碎片。",
                            promisor_id=state.player.player_id,
                            promisee_id="vidalia",
                            due_in_turns=3,
                        )
                    ],
                    witness_ids=[state.player.player_id, "vidalia"],
                )
            ],
        )


@pytest.mark.asyncio
async def test_approved_proposal_updates_state_and_event_in_one_commit(tmp_path) -> None:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'approved.db'}")
    await create_schema(engine)
    session_factory = create_async_session_factory(engine)
    repository = SqlAlchemyGameRepository(session_factory)
    initial = GameState(
        session_id="approved-session",
        player=PlayerState(player_id="player", inventory=["dust_token"]),
    )
    await repository.create_or_get_session(initial)
    orchestrator = GameOrchestrator(repository, story_planner=FixedPlanner("dust_token"))

    response = await orchestrator.process_turn(
        PlayerAction(
            session_id=initial.session_id,
            action_id=uuid4(),
            message="把令牌交給維達利亞",
            target_npc_id="vidalia",
            expected_state_version=1,
        )
    )

    stored = await repository.get_state(initial.session_id)
    assert stored is not None
    assert stored.player.inventory == []
    assert stored.npc_states["vidalia"].inventory == ["dust_token"]
    assert response.state.player.inventory == []
    assert len(response.story.established_events) == 1
    async with session_factory() as database:
        event_count = await database.scalar(select(func.count()).select_from(GameEventRecord))
        action_record = await database.scalar(select(ActionRecord))
    assert event_count == 1
    assert action_record is not None
    assert action_record.resolution_json[0]["reason_code"] == "approved"
    await engine.dispose()


@pytest.mark.asyncio
async def test_rejected_proposal_advances_turn_without_mutating_facts(tmp_path) -> None:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'rejected.db'}")
    await create_schema(engine)
    session_factory = create_async_session_factory(engine)
    repository = SqlAlchemyGameRepository(session_factory)
    initial = GameState(
        session_id="rejected-session",
        player=PlayerState(player_id="player", inventory=[]),
    )
    await repository.create_or_get_session(initial)
    orchestrator = GameOrchestrator(repository, story_planner=FixedPlanner("invented_relic"))

    response = await orchestrator.process_turn(
        PlayerAction(
            session_id=initial.session_id,
            action_id=uuid4(),
            message="我把不存在的寶物交出去",
            target_npc_id="vidalia",
            expected_state_version=1,
        )
    )

    stored = await repository.get_state(initial.session_id)
    assert stored is not None
    assert stored.turn_count == 1
    assert stored.player.inventory == []
    assert stored.npc_states["vidalia"].inventory == []
    assert response.story.established_events == []
    assert all("invented_relic" not in line.text for line in response.story.dialogue)
    async with session_factory() as database:
        event_count = await database.scalar(select(func.count()).select_from(GameEventRecord))
        action_record = await database.scalar(select(ActionRecord))
    assert event_count == 0
    assert action_record is not None
    assert action_record.resolution_json[0]["reason_code"] == "item_not_owned"
    assert "resolution_json" not in response.model_dump(mode="json")
    await engine.dispose()


@pytest.mark.asyncio
async def test_approved_commitment_is_saved_once_with_source_event(tmp_path) -> None:
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'commitment.db'}")
    await create_schema(engine)
    session_factory = create_async_session_factory(engine)
    repository = SqlAlchemyGameRepository(session_factory)
    initial = GameState(
        session_id="commitment-session",
        player=PlayerState(player_id="player"),
    )
    await repository.create_or_get_session(initial)
    orchestrator = GameOrchestrator(repository, story_planner=CommitmentPlanner())
    action = PlayerAction(
        session_id=initial.session_id,
        action_id=uuid4(),
        message="我答應帶回地圖碎片",
        target_npc_id="vidalia",
        expected_state_version=1,
    )

    first = await orchestrator.process_turn(action)
    replay = await orchestrator.process_turn(action)

    assert replay == first
    async with session_factory() as database:
        commitments = list((await database.execute(select(CommitmentRecord))).scalars())
        events = list((await database.execute(select(GameEventRecord))).scalars())
        memories = list((await database.execute(select(MemoryRecord))).scalars())
    assert len(commitments) == 1
    assert len(events) == 1
    assert commitments[0].summary == "玩家答應在三回合內帶回地圖碎片。"
    assert commitments[0].created_turn == 1
    assert commitments[0].due_turn == 4
    assert commitments[0].source_id == events[0].event_id
    assert {memory.memory_type for memory in memories} == {"interaction", "observed_event"}
    assert all(memory.npc_id == "vidalia" for memory in memories)
    await engine.dispose()
