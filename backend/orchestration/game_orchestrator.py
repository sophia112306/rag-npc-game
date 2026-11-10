"""Coordinate the persisted proposal, rule-resolution, and response flow."""

from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from backend.content.demo_story import find_available_demo_story_choice
from backend.database.repository import (
    ActionIdConflictError as RepositoryActionIdConflictError,
    CommittedGameEvent,
    PersistentSessionNotFoundError,
    PersistentStateVersionConflictError,
    action_request_digest,
)
from backend.modules.proposal_resolver import ProposalResolution, ProposalResolver
from backend.orchestration.player_choices import (
    build_player_choices,
    player_choice_action_matches,
)
from backend.orchestration.demo_story_director import (
    build_demo_story_proposal,
    story_choice_action_matches,
)
from backend.schemas.api_response import GameTurnResponse
from backend.schemas.game_state import GameState, PlayerState
from backend.schemas.parsed_action import ActionType, ParsedAction
from backend.schemas.player_action import ActionMode, PlayerAction
from backend.schemas.player_choice import PlayerChoice
from backend.schemas.player_view import project_player_view
from backend.schemas.progression import PlayerQuestView
from backend.schemas.story import (
    DialogueLine,
    ProposalDecision,
    ResolvedStory,
    SpeakerType,
    StoryProposal,
)


class SessionNotFoundError(LookupError):
    """Raised when an API request references an unknown game session."""


class StateVersionConflictError(RuntimeError):
    """Raised when a player action was created from a stale state snapshot."""

    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(f"Expected state version {expected}, but the current version is {actual}")


class ActionIdConflictError(RuntimeError):
    """Raised when one action ID is reused with different effective content."""

    def __init__(self, action_id: UUID) -> None:
        self.action_id = action_id
        super().__init__(f"Action '{action_id}' was already used with different content")


class StoryChoiceUnavailableError(LookupError):
    """Raised when a choice is stale, forged, or unavailable in current state."""


class StoryChoiceMismatchError(ValueError):
    """Raised when a valid choice ID is attached to altered action content."""


class GameRepository(Protocol):
    """Persistence operations required by the orchestrator."""

    async def create_or_get_session(self, initial_state: GameState) -> GameState: ...

    async def get_state(self, session_id: str) -> GameState | None: ...

    async def get_completed_action(
        self,
        session_id: str,
        action_id: UUID,
        request_digest: str,
    ) -> GameTurnResponse | None: ...

    async def get_player_quests(self, session_id: str) -> list[PlayerQuestView]: ...

    async def commit_turn(
        self,
        action: PlayerAction,
        request_digest: str,
        updated_state: GameState,
        response: GameTurnResponse,
        approved_events: Sequence[CommittedGameEvent] = (),
        proposal_decisions: Sequence[ProposalDecision] = (),
    ) -> GameTurnResponse: ...


class StoryPlanner(Protocol):
    """Replaceable source of untrusted story and event proposals."""

    async def propose(
        self,
        action: PlayerAction,
        parsed_action: ParsedAction,
        state: GameState,
    ) -> StoryProposal: ...


class GameOrchestrator:
    """Coordinate input parsing, story generation, and state updates."""

    def __init__(
        self,
        repository: GameRepository,
        story_planner: StoryPlanner,
        proposal_resolver: ProposalResolver | None = None,
    ) -> None:
        self._repository = repository
        self._story_planner = story_planner
        self._proposal_resolver = proposal_resolver or ProposalResolver()

    async def start_game(self, session_id: str) -> GameState:
        """Create a deterministic initial state or resume an existing session."""

        initial_state = GameState(
            session_id=session_id,
            current_scene_id="minglin",
            player=PlayerState(
                player_id=f"{session_id}-player",
                name="玩家",
            ),
        )
        initial_state.npc_states["vidalia"].met = True
        return await self._repository.create_or_get_session(initial_state)

    async def process_turn(self, action: PlayerAction) -> GameTurnResponse:
        """Process one turn through the temporary integration pipeline."""

        request_digest = action_request_digest(action)
        try:
            cached = await self._repository.get_completed_action(
                action.session_id,
                action.action_id,
                request_digest,
            )
            if cached is not None:
                return cached
        except RepositoryActionIdConflictError as exc:
            raise ActionIdConflictError(exc.action_id) from exc

        state = await self.get_state(action.session_id)
        if action.expected_state_version != state.state_version:
            raise StateVersionConflictError(action.expected_state_version, state.state_version)

        parsed_action = self._parse_action(action)
        if action.story_choice_id:
            try:
                quests = await self._repository.get_player_quests(action.session_id)
            except PersistentSessionNotFoundError as exc:
                raise SessionNotFoundError(str(exc)) from exc
            player_choice = next(
                (
                    choice
                    for choice in build_player_choices(state, quests)
                    if choice.choice_id == action.story_choice_id
                ),
                None,
            )
            if player_choice is None:
                raise StoryChoiceUnavailableError(
                    f"Story choice '{action.story_choice_id}' is not available in the current state"
                )
            if not player_choice_action_matches(action, player_choice):
                raise StoryChoiceMismatchError(
                    f"Story choice '{action.story_choice_id}' does not match its authoritative action"
                )
            story_choice = find_available_demo_story_choice(
                state,
                action.story_choice_id,
            )
            if story_choice and story_choice_action_matches(action, story_choice):
                proposal = build_demo_story_proposal(action, state, story_choice)
            else:
                proposal = await self._story_planner.propose(
                    action,
                    parsed_action,
                    state.model_copy(deep=True),
                )
        else:
            proposal = await self._story_planner.propose(
                action,
                parsed_action,
                state.model_copy(deep=True),
            )
        self._validate_proposal_envelope(proposal, state)
        resolution = self._proposal_resolver.resolve(state, proposal)
        updated_state = self._advance_turn(resolution.updated_state)
        story = self._render_resolved_story(proposal, resolution)
        response = GameTurnResponse(
            session_id=action.session_id,
            turn_number=updated_state.turn_count,
            parsed_action=parsed_action,
            story=story,
            state=project_player_view(updated_state),
        )

        try:
            return await self._repository.commit_turn(
                action,
                request_digest,
                updated_state,
                response,
                approved_events=self._committed_events(resolution),
                proposal_decisions=resolution.decisions,
            )
        except RepositoryActionIdConflictError as exc:
            raise ActionIdConflictError(exc.action_id) from exc
        except PersistentSessionNotFoundError as exc:
            raise SessionNotFoundError(str(exc)) from exc
        except PersistentStateVersionConflictError as exc:
            raise StateVersionConflictError(exc.expected, exc.actual) from exc

    async def get_state(self, session_id: str) -> GameState:
        """Load a state snapshot from the temporary store."""

        state = await self._repository.get_state(session_id)
        if state is None:
            raise SessionNotFoundError(f"Session '{session_id}' does not exist")
        return state

    async def get_player_quests(self, session_id: str) -> list[PlayerQuestView]:
        try:
            return await self._repository.get_player_quests(session_id)
        except PersistentSessionNotFoundError as exc:
            raise SessionNotFoundError(str(exc)) from exc

    async def get_player_choices(self, session_id: str) -> list[PlayerChoice]:
        """Return state-aware shortcuts without exposing hidden rules or memories."""

        state = await self.get_state(session_id)
        try:
            quests = await self._repository.get_player_quests(session_id)
        except PersistentSessionNotFoundError as exc:
            raise SessionNotFoundError(str(exc)) from exc

        return build_player_choices(state, quests)

    @staticmethod
    def _parse_action(action: PlayerAction) -> ParsedAction:
        """Create an M1 deterministic placeholder until C's parser is integrated."""

        text = action.message.strip().lower()
        action_type = ActionType.DIALOGUE
        intent = "dialogue"

        if action.action_mode == ActionMode.MOVEMENT:
            action_type, intent = ActionType.MOVEMENT, "move"
        elif action.action_mode == ActionMode.INTERACTION:
            action_type, intent = ActionType.INTERACTION, "interact"
        elif any(keyword in text for keyword in ("使用", "道具", "use")):
            action_type, intent = ActionType.USE_ITEM, "use_item"
        elif any(keyword in text for keyword in ("查看", "觀察", "調查", "inspect")):
            action_type, intent = ActionType.INSPECT, "inspect"

        target_ids = []
        if action.action_mode == ActionMode.MOVEMENT and action.destination_scene_id:
            target_ids.append(action.destination_scene_id)
        elif action.target_npc_id:
            target_ids.append(action.target_npc_id)

        parameters = {
            "action_id": str(action.action_id),
            "input_type": action.input_type.value,
            "action_mode": action.action_mode.value,
        }
        if action.destination_scene_id:
            parameters["destination_scene_id"] = action.destination_scene_id
        if action.story_choice_id:
            parameters["story_choice_id"] = action.story_choice_id

        return ParsedAction(
            intent=intent,
            action_type=action_type,
            target_ids=target_ids,
            parameters=parameters,
            confidence=1.0,
        )

    @staticmethod
    def _advance_turn(state: GameState) -> GameState:
        """Advance only integration metadata; no AI proposal may mutate game facts."""

        updated_state = state.model_copy(deep=True)
        updated_state.turn_count += 1
        updated_state.phase_turns += 1
        updated_state.state_version += 1
        updated_state.updated_at = datetime.now(timezone.utc)
        return updated_state

    @staticmethod
    def _validate_proposal_envelope(proposal: StoryProposal, state: GameState) -> None:
        if proposal.session_id != state.session_id:
            raise ValueError("Story proposal session does not match the authoritative state")
        if proposal.turn_number != state.turn_count + 1:
            raise ValueError("Story proposal turn does not match the next authoritative turn")

    @staticmethod
    def _render_resolved_story(
        proposal: StoryProposal,
        resolution: ProposalResolution,
    ) -> ResolvedStory:
        """Keep NPC speech subjective and describe objective effects deterministically."""

        dialogue = list(proposal.proposed_dialogue)
        for event in resolution.established_events:
            if event.visibility.get("audience") == "player":
                dialogue.append(
                    DialogueLine(
                        speaker_type=SpeakerType.NARRATOR,
                        speaker_name="系統",
                        text=event.description,
                    )
                )
        return ResolvedStory(
            dialogue=dialogue,
            established_events=[
                event
                for event in resolution.established_events
                if event.visibility.get("audience") == "player"
            ],
        )

    @staticmethod
    def _committed_events(
        resolution: ProposalResolution,
    ) -> tuple[CommittedGameEvent, ...]:
        return tuple(
            CommittedGameEvent(
                event_id=str(event.event_id),
                event_type=event.event_type,
                description=event.description,
                actor_id=event.actor_id,
                target_id=event.target_id,
                cause_event_id=str(event.cause_event_id) if event.cause_event_id else None,
                effect=event.effect,
                visibility=event.visibility,
            )
            for event in resolution.established_events
        )
