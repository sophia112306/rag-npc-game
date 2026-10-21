"""Coordinate the game-turn flow while domain modules are being integrated."""

from datetime import datetime, timezone
from typing import Any

from backend.schemas.api_response import GameTurnResponse
from backend.schemas.game_state import GameState, NPCState, PlayerState, SceneState
from backend.schemas.parsed_action import ActionType, ParsedAction
from backend.schemas.player_action import PlayerAction
from backend.schemas.story import (
    DialogueLine,
    EventProposal,
    SpeakerType,
    StoryProposal,
)


class SessionNotFoundError(LookupError):
    """Raised when an API request references an unknown game session."""


class InMemoryGameStateStore:
    """Temporary state store used until the database repositories are ready."""

    def __init__(self) -> None:
        self._states: dict[str, GameState] = {}

    async def get(self, session_id: str) -> GameState | None:
        state = self._states.get(session_id)
        return state.model_copy(deep=True) if state else None

    async def save(self, state: GameState) -> GameState:
        self._states[state.session_id] = state.model_copy(deep=True)
        return state.model_copy(deep=True)


class GameOrchestrator:
    """Coordinate input parsing, story generation, and state updates."""

    def __init__(self, state_store: InMemoryGameStateStore | None = None) -> None:
        self._state_store = state_store or InMemoryGameStateStore()

    async def start_game(self, session_id: str) -> GameState:
        """Create a deterministic initial state or resume an existing session."""

        existing_state = await self._state_store.get(session_id)
        if existing_state is not None:
            return existing_state

        initial_state = GameState(
            session_id=session_id,
            player=PlayerState(
                player_id=f"{session_id}-player",
                display_name="玩家",
                current_scene_id="minglin",
            ),
            npcs={
                "guide": NPCState(
                    npc_id="guide",
                    name="引路人",
                    current_scene_id="minglin",
                    emotion="neutral",
                )
            },
            current_scene=SceneState(
                scene_id="minglin",
                name="鳴霖",
                available_exit_ids=["liuchen_valley", "lieyi_plain"],
                active_npc_ids=["guide"],
            ),
        )
        return await self._state_store.save(initial_state)

    async def process_turn(self, action: PlayerAction) -> GameTurnResponse:
        """Process one turn through the temporary integration pipeline."""

        state = await self.get_state(action.session_id)
        parsed_action = self._parse_action(action)
        updated_state = self._apply_action(state, action, parsed_action)
        story = self._build_placeholder_story(action, parsed_action, updated_state)

        await self._state_store.save(updated_state)
        return GameTurnResponse(
            session_id=action.session_id,
            turn_number=updated_state.turn_number,
            parsed_action=parsed_action,
            story=story,
            state=updated_state,
        )

    async def get_state(self, session_id: str) -> GameState:
        """Load a state snapshot from the temporary store."""

        state = await self._state_store.get(session_id)
        if state is None:
            raise SessionNotFoundError(f"Session '{session_id}' does not exist")
        return state

    @staticmethod
    def _parse_action(action: PlayerAction) -> ParsedAction:
        """Parse a few common phrases without calling an AI model yet."""

        text = action.text.strip().lower()
        action_type = ActionType.ASK
        confidence = 0.55

        if any(keyword in text for keyword in ("幫助", "指令", "help")):
            action_type, confidence = ActionType.HELP, 0.95
        elif any(keyword in text for keyword in ("移動", "前往", "去", "move", "go ")):
            action_type, confidence = ActionType.MOVE, 0.85
        elif any(keyword in text for keyword in ("使用", "使用道具", "use")):
            action_type, confidence = ActionType.USE_ITEM, 0.8
        elif any(keyword in text for keyword in ("攻擊", "攻打", "attack")):
            action_type, confidence = ActionType.ATTACK, 0.8
        elif any(keyword in text for keyword in ("互動", "交談", "詢問", "問", "ask")):
            action_type, confidence = ActionType.INTERACT, 0.75

        return ParsedAction(
            source_action_id=action.action_id,
            action_type=action_type,
            target=action.text if action_type == ActionType.MOVE else None,
            parameters={"input_type": action.input_type.value},
            confidence=confidence,
        )

    @staticmethod
    def _apply_action(
        state: GameState,
        action: PlayerAction,
        parsed_action: ParsedAction,
    ) -> GameState:
        """Apply only safe demo state changes until C's rules are connected."""

        updated_state = state.model_copy(deep=True)
        updated_state.turn_number += 1
        updated_state.updated_at = datetime.now(timezone.utc)
        updated_state.world_flags.update(
            {
                "last_action_id": str(action.action_id),
                "last_action_type": parsed_action.action_type.value,
                "last_action_text": action.text,
            }
        )
        return updated_state

    @staticmethod
    def _build_placeholder_story(
        action: PlayerAction,
        parsed_action: ParsedAction,
        state: GameState,
    ) -> StoryProposal:
        """Return a typed placeholder until B's story engine is connected."""

        dialogue = DialogueLine(
            speaker_type=SpeakerType.NPC,
            speaker_id="guide",
            speaker_name="引路人",
            text=(
                f"我收到你的行動：「{action.text}」。"
                "目前先以測試流程回應，之後會接上 AI 劇情生成。"
            ),
            emotion="neutral",
        )
        event = EventProposal(
            event_type="player_action_received",
            description="The backend received a player action in the integration skeleton.",
            actor_id=state.player.player_id,
            payload={"action_type": parsed_action.action_type.value},
        )
        return StoryProposal(
            session_id=action.session_id,
            turn_number=state.turn_number,
            dialogue=[dialogue],
            event_proposals=[event],
        )
