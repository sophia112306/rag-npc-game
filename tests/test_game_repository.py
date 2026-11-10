"""Transactional persistence tests for the M2a game repository."""

from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from backend.database import create_async_session_factory, create_database_engine, create_schema
from backend.database.models import ActionRecord, DialogueRecord, GameEventRecord, GameSessionRecord
from backend.database.repository import (
    ActionIdConflictError,
    CommittedGameEvent,
    PersistentStateVersionConflictError,
    SqlAlchemyGameRepository,
    action_request_digest,
)
from backend.schemas.api_response import GameTurnResponse
from backend.schemas.game_state import GameState
from backend.schemas.parsed_action import ParsedAction
from backend.schemas.player_action import PlayerAction
from backend.schemas.player_view import project_player_view
from backend.schemas.story import DialogueLine, ResolvedStory, SpeakerType


def make_action(session_id: str, *, message: str = "你好", version: int = 1, action_id=None) -> PlayerAction:
    return PlayerAction(
        session_id=session_id,
        action_id=action_id or uuid4(),
        message=message,
        target_npc_id="vidalia",
        expected_state_version=version,
    )


def make_turn(action: PlayerAction, state: GameState) -> tuple[GameState, GameTurnResponse]:
    updated = state.model_copy(deep=True)
    updated.turn_count += 1
    updated.phase_turns += 1
    updated.state_version += 1
    parsed = ParsedAction(
        intent="dialogue",
        target_ids=["vidalia"],
        parameters={"action_id": str(action.action_id)},
    )
    story = ResolvedStory(
        dialogue=[
            DialogueLine(
                speaker_type=SpeakerType.NPC,
                speaker_id="vidalia",
                speaker_name="維達利亞",
                text="測試回覆",
            )
        ],
    )
    return (
        updated,
        GameTurnResponse(
            session_id=state.session_id,
            turn_number=updated.turn_count,
            parsed_action=parsed,
            story=story,
            state=project_player_view(updated),
        ),
    )


@pytest_asyncio.fixture
async def repository_context(tmp_path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'game.db'}"
    engine = create_database_engine(database_url)
    await create_schema(engine)
    session_factory = create_async_session_factory(engine)
    yield SqlAlchemyGameRepository(session_factory), session_factory, database_url
    await engine.dispose()


@pytest.mark.asyncio
async def test_session_and_completed_turn_survive_new_engine(repository_context) -> None:
    repository, _session_factory, database_url = repository_context
    initial = GameState(session_id="persistent-session", current_scene_id="minglin")
    await repository.create_or_get_session(initial)
    action = make_action(initial.session_id)
    updated, response = make_turn(action, initial)
    await repository.commit_turn(
        action,
        action_request_digest(action),
        updated,
        response,
        approved_events=[
            CommittedGameEvent(
                event_type="test_event",
                description="An approved test event",
                actor_id="player",
            )
        ],
    )

    replacement_engine = create_database_engine(database_url)
    replacement = SqlAlchemyGameRepository(create_async_session_factory(replacement_engine))
    restored = await replacement.get_state(initial.session_id)
    cached = await replacement.get_completed_action(
        initial.session_id,
        action.action_id,
        action_request_digest(action),
    )

    assert restored is not None
    assert restored.state_version == 2
    assert restored.turn_count == 1
    assert cached == response
    await replacement_engine.dispose()


@pytest.mark.asyncio
async def test_same_action_id_with_different_content_is_rejected(repository_context) -> None:
    repository, _session_factory, _database_url = repository_context
    initial = GameState(session_id="digest-session")
    await repository.create_or_get_session(initial)
    action = make_action(initial.session_id)
    updated, response = make_turn(action, initial)
    await repository.commit_turn(action, action_request_digest(action), updated, response)
    changed = make_action(initial.session_id, message="不同內容", action_id=action.action_id)

    with pytest.raises(ActionIdConflictError):
        await repository.get_completed_action(
            changed.session_id,
            changed.action_id,
            action_request_digest(changed),
        )


@pytest.mark.asyncio
async def test_stale_version_does_not_create_a_second_turn(repository_context) -> None:
    repository, session_factory, _database_url = repository_context
    initial = GameState(session_id="version-session")
    await repository.create_or_get_session(initial)
    first = make_action(initial.session_id)
    first_updated, first_response = make_turn(first, initial)
    await repository.commit_turn(
        first,
        action_request_digest(first),
        first_updated,
        first_response,
    )
    stale = make_action(initial.session_id, message="第二個動作", version=1)
    stale_updated, stale_response = make_turn(stale, initial)

    with pytest.raises(PersistentStateVersionConflictError):
        await repository.commit_turn(
            stale,
            action_request_digest(stale),
            stale_updated,
            stale_response,
        )

    async with session_factory() as database:
        action_count = await database.scalar(select(func.count()).select_from(ActionRecord))
        dialogue_count = await database.scalar(select(func.count()).select_from(DialogueRecord))
    assert action_count == 1
    assert dialogue_count == 1


@pytest.mark.asyncio
async def test_failed_event_serialization_rolls_back_entire_turn(repository_context) -> None:
    repository, session_factory, _database_url = repository_context
    initial = GameState(session_id="rollback-session")
    await repository.create_or_get_session(initial)
    action = make_action(initial.session_id)
    invalid_event = CommittedGameEvent(
        event_type="invalid_test_event",
        description="Forces JSON serialization failure",
        effect={"not_json": object()},
    )
    updated, response = make_turn(action, initial)

    with pytest.raises(Exception):
        await repository.commit_turn(
            action,
            action_request_digest(action),
            updated,
            response,
            approved_events=[invalid_event],
        )

    async with session_factory() as database:
        session = await database.get(GameSessionRecord, initial.session_id)
        action_count = await database.scalar(select(func.count()).select_from(ActionRecord))
        dialogue_count = await database.scalar(select(func.count()).select_from(DialogueRecord))
        event_count = await database.scalar(select(func.count()).select_from(GameEventRecord))
    assert session is not None
    assert session.state_version == 1
    assert session.turn_count == 0
    assert action_count == 0
    assert dialogue_count == 0
    assert event_count == 0
