"""State-aware deterministic story generation tests."""

from uuid import uuid4

import pytest

from backend.generation.rule_based_planner import RuleBasedStoryPlanner
from backend.schemas.content import MemoryItem, NPCGenerationContext
from backend.schemas.game_state import GameState, PlayerState
from backend.schemas.parsed_action import ParsedAction
from backend.schemas.player_action import PlayerAction
from backend.schemas.progression import (
    ProgressionSourceKind,
    QuestItem,
    QuestStatus,
)


class FixedContextProvider:
    def __init__(self, context: NPCGenerationContext) -> None:
        self.context = context
        self.calls: list[tuple[str, str, int]] = []

    async def get_generation_context(self, session_id, npc_id, current_turn):
        self.calls.append((session_id, npc_id, current_turn))
        return self.context


def make_context(**changes) -> NPCGenerationContext:
    values = {
        "npc_id": "vidalia",
        "setting_version": 1,
        "public_profile": {
            "name": "維達利亞",
            "scene_name": "鳴霖・平衡議會",
        },
        "private_profile": {},
        "knowledge": [],
        "memories": [],
        "active_goals": [],
        "active_commitments": [],
        "active_quests": [],
        "missing_data": ["character_definition_incomplete"],
    }
    values.update(changes)
    return NPCGenerationContext(**values)


def make_inputs(
    message: str,
    *,
    turn_count: int = 0,
    inventory: list[str] | None = None,
) -> tuple[PlayerAction, ParsedAction, GameState]:
    state = GameState(
        session_id="rule-session",
        turn_count=turn_count,
        state_version=turn_count + 1,
        current_scene_id="minglin",
        player=PlayerState(
            player_id="rule-player",
            name="玩家",
            inventory=inventory or [],
        ),
    )
    action = PlayerAction(
        session_id=state.session_id,
        action_id=uuid4(),
        message=message,
        target_npc_id="vidalia",
        expected_state_version=state.state_version,
    )
    return action, ParsedAction(intent="dialogue", target_ids=["vidalia"]), state


@pytest.mark.asyncio
async def test_greeting_changes_with_persisted_turn_context() -> None:
    first_provider = FixedContextProvider(make_context())
    first_planner = RuleBasedStoryPlanner(first_provider)
    first_action, parsed, first_state = make_inputs("你好")

    first = await first_planner.propose(first_action, parsed, first_state)

    memory = MemoryItem(
        memory_id="memory-1",
        content="玩家說：「你好」",
        memory_type="interaction",
        occurred_turn=1,
        importance=10,
        provenance={},
    )
    returning_provider = FixedContextProvider(make_context(memories=[memory]))
    returning_planner = RuleBasedStoryPlanner(returning_provider)
    returning_action, parsed, returning_state = make_inputs("你好", turn_count=1)

    returning = await returning_planner.propose(
        returning_action,
        parsed,
        returning_state,
    )

    assert first.proposed_dialogue[0].text != returning.proposed_dialogue[0].text
    assert "開發替身" not in first.proposed_dialogue[0].text
    assert "先前的交談" in returning.proposed_dialogue[0].text


@pytest.mark.asyncio
async def test_help_request_proposes_one_persistable_quest() -> None:
    planner = RuleBasedStoryPlanner(FixedContextProvider(make_context()))
    action, parsed, state = make_inputs("有什麼需要我幫忙的任務？")

    proposal = await planner.propose(action, parsed, state)

    assert len(proposal.event_proposals) == 1
    operation = proposal.event_proposals[0].operations[0]
    assert operation.operation_type == "offer_quest"
    assert operation.giver_id == "vidalia"
    assert operation.recipient_id == "rule-player"
    assert "鳴霖・平衡議會" in operation.title


@pytest.mark.asyncio
async def test_existing_player_visible_quest_is_referenced_without_duplicate() -> None:
    quest = QuestItem(
        quest_id="quest-1",
        title="既有任務",
        summary="回報已確認的異常。",
        giver_id="vidalia",
        recipient_id="rule-player",
        status=QuestStatus.OFFERED,
        created_turn=1,
        due_turn=6,
        source_kind=ProgressionSourceKind.ESTABLISHED_EVENT,
        source_id="event-1",
        visibility="player",
        provenance={},
    )
    planner = RuleBasedStoryPlanner(
        FixedContextProvider(make_context(active_quests=[quest]))
    )
    action, parsed, state = make_inputs("任務是什麼？", turn_count=1)

    proposal = await planner.propose(action, parsed, state)

    assert proposal.event_proposals == []
    assert "既有任務" in proposal.proposed_dialogue[0].text


@pytest.mark.asyncio
async def test_recall_uses_interaction_memory_without_revealing_observed_secret() -> None:
    memories = [
        MemoryItem(
            memory_id="interaction-1",
            content="玩家說：「我會再回來」",
            memory_type="interaction",
            occurred_turn=1,
            importance=10,
            provenance={},
        ),
        MemoryItem(
            memory_id="secret-event",
            content="不可向玩家公開的目擊事件",
            memory_type="observed_event",
            occurred_turn=2,
            importance=20,
            provenance={},
        ),
    ]
    planner = RuleBasedStoryPlanner(FixedContextProvider(make_context(memories=memories)))
    action, parsed, state = make_inputs("你還記得之前說過什麼嗎？", turn_count=2)

    proposal = await planner.propose(action, parsed, state)

    dialogue = proposal.proposed_dialogue[0].text
    assert "我會再回來" in dialogue
    assert "不可向玩家公開" not in dialogue


@pytest.mark.asyncio
async def test_explicit_promise_creates_commitment_proposal() -> None:
    planner = RuleBasedStoryPlanner(FixedContextProvider(make_context()))
    action, parsed, state = make_inputs("我答應會回來報告")

    proposal = await planner.propose(action, parsed, state)

    operation = proposal.event_proposals[0].operations[0]
    assert operation.operation_type == "establish_commitment"
    assert operation.promisor_id == "rule-player"
    assert operation.promisee_id == "vidalia"
    assert "我答應會回來報告" in operation.summary


@pytest.mark.asyncio
async def test_item_transfer_requires_an_owned_item_to_be_named() -> None:
    planner = RuleBasedStoryPlanner(FixedContextProvider(make_context()))
    action, parsed, state = make_inputs(
        "我把 map_fragment 交給你",
        inventory=["map_fragment"],
    )

    proposal = await planner.propose(action, parsed, state)

    operation = proposal.event_proposals[0].operations[0]
    assert operation.operation_type == "transfer_item"
    assert operation.item_id == "map_fragment"
    assert operation.from_entity_id == "rule-player"
    assert operation.to_entity_id == "vidalia"
