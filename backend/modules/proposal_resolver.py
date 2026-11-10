"""Validate whitelisted proposal operations before changing authoritative state."""

from dataclasses import dataclass

from backend.schemas.game_state import GameState
from backend.schemas.story import (
    EstablishedEvent,
    EventProposal,
    ProposalDecision,
    ProposalStatus,
    StoryProposal,
    TransferItemOperation,
)


class ProposalRuleViolation(ValueError):
    """Internal control flow for a proposal rejected by deterministic rules."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class ProposalResolution:
    """Candidate state and auditable decisions produced outside the DB transaction."""

    updated_state: GameState
    decisions: tuple[ProposalDecision, ...]

    @property
    def established_events(self) -> tuple[EstablishedEvent, ...]:
        return tuple(
            decision.established_event
            for decision in self.decisions
            if decision.established_event is not None
        )


class ProposalResolver:
    """Apply only known commands; reject each event atomically on rule failure."""

    def resolve(self, state: GameState, proposal: StoryProposal) -> ProposalResolution:
        candidate = state.model_copy(deep=True)
        decisions: list[ProposalDecision] = []

        for event in proposal.event_proposals:
            event_candidate = candidate.model_copy(deep=True)
            try:
                descriptions = [
                    self._apply_operation(event_candidate, event, operation)
                    for operation in event.operations
                ]
            except ProposalRuleViolation as exc:
                decisions.append(
                    ProposalDecision(
                        proposal_id=event.proposal_id,
                        status=ProposalStatus.REJECTED,
                        reason_code=exc.code,
                        reason=str(exc),
                    )
                )
                continue

            established = EstablishedEvent(
                proposal_id=event.proposal_id,
                event_type=event.event_type,
                description=" ".join(descriptions),
                actor_id=event.actor_id,
                target_id=event.target_id,
                cause_event_id=event.cause_event_id,
                effect={
                    "operations": [operation.model_dump(mode="json") for operation in event.operations]
                },
                visibility={
                    "audience": "player" if event.visible_to_player else "backend",
                    "witness_ids": event.witness_ids,
                },
            )
            decisions.append(
                ProposalDecision(
                    proposal_id=event.proposal_id,
                    status=ProposalStatus.APPROVED,
                    reason_code="approved",
                    reason="All proposed operations passed deterministic validation.",
                    established_event=established,
                )
            )
            candidate = event_candidate

        return ProposalResolution(updated_state=candidate, decisions=tuple(decisions))

    def _apply_operation(
        self,
        state: GameState,
        event: EventProposal,
        operation: TransferItemOperation,
    ) -> str:
        if event.actor_id != operation.from_entity_id:
            raise ProposalRuleViolation(
                "actor_not_item_source",
                "The event actor cannot transfer an item owned by another entity.",
            )
        if event.target_id is not None and event.target_id != operation.to_entity_id:
            raise ProposalRuleViolation(
                "target_mismatch",
                "The event target does not match the transfer recipient.",
            )
        if operation.from_entity_id == operation.to_entity_id:
            raise ProposalRuleViolation(
                "same_item_owner",
                "An item transfer requires two different entities.",
            )

        source_inventory = self._inventory_for(state, operation.from_entity_id)
        target_inventory = self._inventory_for(state, operation.to_entity_id)
        if operation.item_id not in source_inventory:
            raise ProposalRuleViolation(
                "item_not_owned",
                f"Entity '{operation.from_entity_id}' does not own item '{operation.item_id}'.",
            )
        if operation.item_id in target_inventory:
            raise ProposalRuleViolation(
                "duplicate_item_ownership",
                f"Entity '{operation.to_entity_id}' already owns item '{operation.item_id}'.",
            )

        source_inventory.remove(operation.item_id)
        target_inventory.append(operation.item_id)
        return (
            f"Item '{operation.item_id}' transferred from "
            f"'{operation.from_entity_id}' to '{operation.to_entity_id}'."
        )

    @staticmethod
    def _inventory_for(state: GameState, entity_id: str) -> list[str]:
        if entity_id == state.player.player_id:
            return state.player.inventory
        npc = state.npc_states.get(entity_id)
        if npc is None:
            raise ProposalRuleViolation(
                "unknown_entity",
                f"Entity '{entity_id}' is not registered in the current game state.",
            )
        return npc.inventory
