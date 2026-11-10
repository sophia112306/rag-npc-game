"""Deterministic rule-boundary tests for generated event proposals."""

from backend.modules.proposal_resolver import ProposalResolver
from backend.schemas.game_state import GameState
from backend.schemas.story import (
    EstablishCommitmentOperation,
    EventProposal,
    OfferQuestOperation,
    ProposalStatus,
    StoryProposal,
    TransferItemOperation,
)


def make_state() -> GameState:
    state = GameState(session_id="proposal-session")
    state.player.player_id = "player"
    state.player.inventory = ["dust_token", "map_fragment"]
    return state


def make_proposal(*events: EventProposal) -> StoryProposal:
    return StoryProposal(
        session_id="proposal-session",
        turn_number=1,
        event_proposals=list(events),
    )


def transfer_event(
    item_id: str,
    *,
    actor_id: str = "player",
    target_id: str = "vidalia",
    from_entity_id: str = "player",
    to_entity_id: str = "vidalia",
) -> EventProposal:
    return EventProposal(
        event_type="item_exchange",
        description="Generated flavor text is not promoted into an objective fact.",
        actor_id=actor_id,
        target_id=target_id,
        operations=[
            TransferItemOperation(
                item_id=item_id,
                from_entity_id=from_entity_id,
                to_entity_id=to_entity_id,
            )
        ],
        witness_ids=["player", "vidalia"],
    )


def test_existing_item_can_be_transferred_between_registered_entities() -> None:
    state = make_state()

    result = ProposalResolver().resolve(state, make_proposal(transfer_event("dust_token")))

    assert state.player.inventory == ["dust_token", "map_fragment"]
    assert result.updated_state.player.inventory == ["map_fragment"]
    assert result.updated_state.npc_states["vidalia"].inventory == ["dust_token"]
    assert result.decisions[0].status == ProposalStatus.APPROVED
    established = result.established_events[0]
    assert established.effect["operations"][0]["operation_type"] == "transfer_item"
    assert "Generated flavor text" not in established.description


def test_nonexistent_item_is_rejected_without_changing_state() -> None:
    state = make_state()

    result = ProposalResolver().resolve(state, make_proposal(transfer_event("invented_relic")))

    assert result.updated_state == state
    assert result.established_events == ()
    assert result.decisions[0].status == ProposalStatus.REJECTED
    assert result.decisions[0].reason_code == "item_not_owned"


def test_unknown_entity_is_rejected_without_changing_state() -> None:
    state = make_state()
    event = transfer_event(
        "dust_token",
        target_id="invented_npc",
        to_entity_id="invented_npc",
    )

    result = ProposalResolver().resolve(state, make_proposal(event))

    assert result.updated_state == state
    assert result.decisions[0].reason_code == "unknown_entity"


def test_event_operations_are_all_or_nothing() -> None:
    state = make_state()
    event = transfer_event("dust_token")
    event.operations.append(
        TransferItemOperation(
            item_id="invented_relic",
            from_entity_id="player",
            to_entity_id="vidalia",
        )
    )

    result = ProposalResolver().resolve(state, make_proposal(event))

    assert result.updated_state == state
    assert result.established_events == ()
    assert result.decisions[0].reason_code == "item_not_owned"


def test_actor_cannot_transfer_another_entity_item() -> None:
    state = make_state()
    state.npc_states["vidalia"].inventory = ["npc_relic"]
    event = transfer_event(
        "npc_relic",
        actor_id="player",
        from_entity_id="vidalia",
        to_entity_id="player",
        target_id="player",
    )

    result = ProposalResolver().resolve(state, make_proposal(event))

    assert result.updated_state == state
    assert result.decisions[0].reason_code == "actor_not_item_source"


def test_registered_actor_can_establish_a_sourced_commitment_effect() -> None:
    state = make_state()
    event = EventProposal(
        event_type="commitment_created",
        description="Untrusted wording.",
        actor_id="player",
        target_id="vidalia",
        operations=[
            EstablishCommitmentOperation(
                summary="帶回經後端確認存在的地圖碎片。",
                promisor_id="player",
                promisee_id="vidalia",
                due_in_turns=3,
            )
        ],
        witness_ids=["player", "vidalia"],
    )

    result = ProposalResolver().resolve(state, make_proposal(event))

    assert result.decisions[0].status == ProposalStatus.APPROVED
    operation = result.established_events[0].effect["operations"][0]
    assert operation["operation_type"] == "establish_commitment"
    assert operation["created_turn"] == 1
    assert operation["due_turn"] == 4
    assert operation["commitment_id"]


def test_commitment_with_unknown_participant_is_rejected() -> None:
    state = make_state()
    event = EventProposal(
        event_type="commitment_created",
        description="Unknown participant.",
        actor_id="player",
        target_id="invented_npc",
        operations=[
            EstablishCommitmentOperation(
                summary="不應成立。",
                promisor_id="player",
                promisee_id="invented_npc",
            )
        ],
    )

    result = ProposalResolver().resolve(state, make_proposal(event))

    assert result.established_events == ()
    assert result.decisions[0].reason_code == "unknown_entity"


def test_quest_offer_does_not_mark_quest_as_accepted_or_completed() -> None:
    state = make_state()
    event = EventProposal(
        event_type="quest_offered",
        description="Untrusted wording.",
        actor_id="vidalia",
        target_id="player",
        operations=[
            OfferQuestOperation(
                title="測試委託",
                summary="只建立待接受任務。",
                giver_id="vidalia",
                recipient_id="player",
                due_in_turns=2,
            )
        ],
    )

    result = ProposalResolver().resolve(state, make_proposal(event))

    operation = result.established_events[0].effect["operations"][0]
    assert operation["operation_type"] == "offer_quest"
    assert "status" not in operation
    assert operation["due_turn"] == 3
