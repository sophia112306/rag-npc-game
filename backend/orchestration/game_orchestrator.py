"""Coordinate the deterministic M1 game-turn flow."""

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from backend.database.repository import (
    ActionIdConflictError as RepositoryActionIdConflictError,
    PersistentSessionNotFoundError,
    PersistentStateVersionConflictError,
    action_request_digest,
)
from backend.schemas.api_response import GameTurnResponse
from backend.schemas.game_state import GameState, PlayerState
from backend.schemas.parsed_action import ActionType, ParsedAction
from backend.schemas.player_action import ActionMode, PlayerAction
from backend.schemas.story import (
    DialogueLine,
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

    async def commit_turn(
        self,
        action: PlayerAction,
        request_digest: str,
        response: GameTurnResponse,
    ) -> GameTurnResponse: ...


class GameOrchestrator:
    """Coordinate input parsing, story generation, and state updates."""

    def __init__(self, repository: GameRepository) -> None:
        self._repository = repository

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
        updated_state = self._apply_action(state)
        story = self._build_placeholder_story(action, updated_state)
        response = GameTurnResponse(
            session_id=action.session_id,
            turn_number=updated_state.turn_count,
            parsed_action=parsed_action,
            story=story,
            state=updated_state,
        )

        try:
            return await self._repository.commit_turn(action, request_digest, response)
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

        return ParsedAction(
            intent=intent,
            action_type=action_type,
            target_ids=[action.target_npc_id] if action.target_npc_id else [],
            parameters={
                "action_id": str(action.action_id),
                "input_type": action.input_type.value,
                "action_mode": action.action_mode.value,
            },
            confidence=1.0,
        )

    @staticmethod
    def _apply_action(state: GameState) -> GameState:
        """Advance only integration metadata; no AI proposal may mutate game facts."""

        updated_state = state.model_copy(deep=True)
        updated_state.turn_count += 1
        updated_state.phase_turns += 1
        updated_state.state_version += 1
        updated_state.updated_at = datetime.now(timezone.utc)
        return updated_state

    @staticmethod
    def _build_placeholder_story(
        action: PlayerAction,
        state: GameState,
    ) -> StoryProposal:
        """Return an explicit development stub until B's model gateway is connected."""

        dialogue = DialogueLine(
            speaker_type=SpeakerType.NPC,
            speaker_id=action.target_npc_id or "vidalia",
            speaker_name="維達利亞",
            text=(
                f"（開發替身）我收到你的話：「{action.message}」。"
                "目前只驗證前後端流程，真實模型、RAG 與遊戲規則尚未接入。"
            ),
            emotion="neutral",
        )
        return StoryProposal(
            session_id=action.session_id,
            turn_number=state.turn_count,
            dialogue=[dialogue],
            event_proposals=[],
        )
