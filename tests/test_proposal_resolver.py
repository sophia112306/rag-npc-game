"""Deterministic rule-boundary tests for generated event proposals."""

from backend.modules.proposal_resolver import ProposalResolver
from backend.schemas.game_state import GameState
from backend.schemas.story import (
    EventProposal,
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
