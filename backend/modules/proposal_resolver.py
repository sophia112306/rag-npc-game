"""Validate whitelisted proposal operations before changing authoritative state."""

from dataclasses import dataclass
from uuid import uuid4

from backend.content.scenes import can_travel, get_scene
from backend.schemas.game_state import GameState
from backend.schemas.story import (
    ChangeSceneOperation,
    EstablishedEvent,
    EstablishCommitmentOperation,
    EventProposal,
    OfferQuestOperation,
    OperationType,
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
                applied = [
                    self._apply_operation(
                        event_candidate,
                        event,
                        operation,
                        proposal.turn_number,
                    )
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
                description=" ".join(description for description, _effect in applied),
                actor_id=event.actor_id,
                target_id=event.target_id,
                cause_event_id=event.cause_event_id,
                effect={
                    "operations": [effect for _description, effect in applied]
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
        operation: (
            TransferItemOperation
            | EstablishCommitmentOperation
            | OfferQuestOperation
            | ChangeSceneOperation
        ),
        turn_number: int,
    ) -> tuple[str, dict[str, object]]:
        if isinstance(operation, ChangeSceneOperation):
            return self._change_scene(state, event, operation)
        if isinstance(operation, EstablishCommitmentOperation):
            return self._establish_commitment(state, event, operation, turn_number)
        if isinstance(operation, OfferQuestOperation):
            return self._offer_quest(state, event, operation, turn_number)

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
        source_name = self._entity_label(state, operation.from_entity_id)
        target_name = self._entity_label(state, operation.to_entity_id)
        return (
            (
                f"物品「{operation.item_id}」已由「{source_name}」"
                f"移交給「{target_name}」。"
            ),
            operation.model_dump(mode="json"),
        )

    def _establish_commitment(
        self,
        state: GameState,
        event: EventProposal,
        operation: EstablishCommitmentOperation,
        turn_number: int,
    ) -> tuple[str, dict[str, object]]:
        self._require_entity(state, operation.promisor_id)
        self._require_entity(state, operation.promisee_id)
        if event.actor_id != operation.promisor_id:
            raise ProposalRuleViolation(
                "actor_not_promisor",
                "Only the event actor can become the promisor.",
            )
        if event.target_id is not None and event.target_id != operation.promisee_id:
            raise ProposalRuleViolation(
                "target_mismatch",
                "The event target does not match the commitment promisee.",
            )
        if operation.promisor_id == operation.promisee_id:
            raise ProposalRuleViolation(
                "same_commitment_participant",
                "A commitment requires two different participants.",
            )

        commitment_id = str(uuid4())
        due_turn = (
            turn_number + operation.due_in_turns
            if operation.due_in_turns is not None
            else None
        )
        effect: dict[str, object] = {
            "operation_type": OperationType.ESTABLISH_COMMITMENT.value,
            "commitment_id": commitment_id,
            "summary": operation.summary,
            "promisor_id": operation.promisor_id,
            "promisee_id": operation.promisee_id,
            "created_turn": turn_number,
            "due_turn": due_turn,
            "visibility": "player" if event.visible_to_player else "backend",
            "proposal_id": str(event.proposal_id),
        }
        promisor_name = self._entity_label(state, operation.promisor_id)
        promisee_name = self._entity_label(state, operation.promisee_id)
        return (
            (
                f"「{promisor_name}」已向「{promisee_name}」"
                f"建立承諾：{operation.summary}"
            ),
            effect,
        )

    def _change_scene(
        self,
        state: GameState,
        event: EventProposal,
        operation: ChangeSceneOperation,
    ) -> tuple[str, dict[str, object]]:
        if event.actor_id != state.player.player_id:
            raise ProposalRuleViolation(
                "actor_not_player",
                "Only the player can execute a player-triggered scene transition.",
            )
        if event.target_id is not None and event.target_id != operation.destination_scene_id:
            raise ProposalRuleViolation(
                "target_mismatch",
                "The event target does not match the scene destination.",
            )

        source_scene_id = state.current_scene_id
        destination = get_scene(operation.destination_scene_id)
        if destination is None:
            raise ProposalRuleViolation(
                "unknown_scene",
                f"Scene '{operation.destination_scene_id}' is not registered.",
            )
        if source_scene_id == destination.scene_id:
            raise ProposalRuleViolation(
                "same_scene",
                "A scene transition requires a different destination.",
            )
        if not can_travel(source_scene_id, destination.scene_id):
            raise ProposalRuleViolation(
                "scene_not_connected",
                f"Scene '{destination.scene_id}' is not reachable from '{source_scene_id}'.",
            )

        state.current_scene_id = destination.scene_id
        effect: dict[str, object] = {
            "operation_type": OperationType.CHANGE_SCENE.value,
            "source_scene_id": source_scene_id,
            "destination_scene_id": destination.scene_id,
        }
        return (
            f"「{state.player.name}」已抵達「{destination.display_name}」。",
            effect,
        )

    def _offer_quest(
        self,
        state: GameState,
        event: EventProposal,
        operation: OfferQuestOperation,
        turn_number: int,
    ) -> tuple[str, dict[str, object]]:
        self._require_entity(state, operation.giver_id)
        self._require_entity(state, operation.recipient_id)
        if event.actor_id != operation.giver_id:
            raise ProposalRuleViolation("actor_not_quest_giver", "Only the actor can offer a quest.")
        if event.target_id is not None and event.target_id != operation.recipient_id:
            raise ProposalRuleViolation("target_mismatch", "Quest recipient does not match target.")
        if operation.giver_id == operation.recipient_id:
            raise ProposalRuleViolation(
                "same_quest_participant",
                "A quest requires different giver and recipient entities.",
            )

        due_turn = (
            turn_number + operation.due_in_turns
            if operation.due_in_turns is not None
            else None
        )
        effect: dict[str, object] = {
            "operation_type": OperationType.OFFER_QUEST.value,
            "quest_id": str(uuid4()),
            "title": operation.title,
            "summary": operation.summary,
            "giver_id": operation.giver_id,
            "recipient_id": operation.recipient_id,
            "created_turn": turn_number,
            "due_turn": due_turn,
            "visibility": "player" if event.visible_to_player else "backend",
            "proposal_id": str(event.proposal_id),
        }
        giver_name = self._entity_label(state, operation.giver_id)
        recipient_name = self._entity_label(state, operation.recipient_id)
        return (
            (
                f"「{giver_name}」已向「{recipient_name}」"
                f"提出任務「{operation.title}」。"
            ),
            effect,
        )

    @staticmethod
    def _require_entity(state: GameState, entity_id: str) -> None:
        if entity_id == state.player.player_id or entity_id in state.npc_states:
            return
        raise ProposalRuleViolation(
            "unknown_entity",
            f"Entity '{entity_id}' is not registered in the current game state.",
        )

    @staticmethod
    def _entity_label(state: GameState, entity_id: str) -> str:
        if entity_id == state.player.player_id:
            return state.player.name or entity_id
        npc = state.npc_states.get(entity_id)
        return npc.name if npc and npc.name else entity_id

    @classmethod
    def _inventory_for(cls, state: GameState, entity_id: str) -> list[str]:
        cls._require_entity(state, entity_id)
        if entity_id == state.player.player_id:
            return state.player.inventory
        return state.npc_states[entity_id].inventory
