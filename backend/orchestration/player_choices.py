"""Build player-visible shortcuts from authoritative story and scene data."""

from backend.content.characters import npc_is_present
from backend.content.demo_story import available_demo_story_choices, available_npc_dialogue_choices
from backend.content.scenes import require_scene, travel_destinations
from backend.generation.gateway import TurnGuidance, TurnGuidanceAction
from backend.schemas.game_state import GameState
from backend.schemas.player_action import ActionMode, PlayerAction
from backend.schemas.player_choice import PlayerChoice
from backend.schemas.progression import PlayerQuestView


def npc_available_in_state(npc_id: str, state: GameState) -> bool:
    """Apply story-gated presence on top of the scene's canonical NPC list."""

    if not npc_is_present(npc_id, state.current_scene_id):
        return False
    if state.current_scene_id == "minglin":
        if state.story_progress.node_id in {"minglin_arrival", "minglin_path_open"}:
            return npc_id == "andre"
        if state.story_progress.node_id in {"minglin_council", "minglin_orientation", "minglin_briefed"}:
            return npc_id == "vidalia"
    return True


def build_player_choices(
    state: GameState,
    quests: list[PlayerQuestView],
    npc_id: str | None = None,
) -> list[PlayerChoice]:
    """Return a small contextual set; movement comes from the scene graph."""

    if npc_id is not None:
        if not npc_available_in_state(npc_id, state):
            return []
        if state.story_progress.node_id in {"fissure_arrival", "minglin_arrival", "minglin_council", "minglin_orientation"}:
            return [
                choice.to_player_choice()
                for choice in available_demo_story_choices(state)
                if choice.target_npc_id == npc_id
            ]
        if npc_id != "vidalia" or state.current_scene_id != "minglin":
            return [choice.to_player_choice() for choice in available_npc_dialogue_choices(state, npc_id)]

    story_choices = available_demo_story_choices(state)
    if story_choices:
        if quests and state.story_progress.node_id in {
            "minglin_arrival",
            "minglin_briefed",
        }:
            # Keep existing quest dialogue, but travel must also advance the
            # story node. A plain scene change stranded legacy quest sessions.
            travel = [choice.to_player_choice() for choice in story_choices if choice.destination_scene_id]
            return [*_dialogue_choices(state, quests)[:2], *travel[:2]]
        return [choice.to_player_choice() for choice in story_choices]

    travel = _travel_choices(state.current_scene_id)
    dialogue_limit = max(1, 4 - len(travel))
    return [*_dialogue_choices(state, quests)[:dialogue_limit], *travel]


def build_turn_guidance(
    state: GameState,
    choices: list[PlayerChoice],
) -> TurnGuidance:
    """Project the current objective and legal actions for model dialogue.

    This deliberately reuses player-visible navigation and choices instead of
    serializing GameState, which includes author-only facts and hidden flags.
    """

    # Import here because player_view derives its navigation through this
    # module. At call time both modules have completed initialization.
    from backend.schemas.player_view import project_navigation

    navigation = project_navigation(state)
    return TurnGuidance(
        objective=navigation.objective,
        scene_name=require_scene(state.current_scene_id).display_name,
        available_actions=[
            TurnGuidanceAction(
                label=choice.label,
                action_mode=choice.action_mode,
                destination_scene_id=choice.destination_scene_id,
                target_npc_id=choice.target_npc_id,
            )
            for choice in choices[:8]
        ],
    )


def player_choice_action_matches(
    action: PlayerAction,
    choice: PlayerChoice,
) -> bool:
    """Bind every clickable choice ID to the exact server-issued action."""

    return (
        action.message == choice.message
        and action.target_npc_id == choice.target_npc_id
        and action.action_mode == choice.action_mode
        and action.destination_scene_id == choice.destination_scene_id
    )


def _dialogue_choices(
    state: GameState,
    quests: list[PlayerQuestView],
) -> list[PlayerChoice]:
    target_npc_id = "vidalia"
    if quests:
        current_quest = quests[0]
        return [
            PlayerChoice(
                choice_id="ask_current_quest",
                label=f"詢問「{current_quest.title}」",
                message="請再告訴我目前任務的內容。",
                target_npc_id=target_npc_id,
            ),
            PlayerChoice(
                choice_id="promise_to_report",
                label="承諾完成後回報",
                message="我答應會調查這項異常，完成後回來報告。",
                target_npc_id=target_npc_id,
            ),
        ]

    contextual = PlayerChoice(
        choice_id="recall_conversation" if state.turn_count else "ask_about_anomaly",
        label="回想先前對話" if state.turn_count else "詢問世界異象",
        message=(
            "你還記得我們之前說過什麼嗎？"
            if state.turn_count
            else "你提到世界出現異象，目前能確認的是什麼？"
        ),
        target_npc_id=target_npc_id,
    )
    return [
        PlayerChoice(
            choice_id="ask_location",
            label="詢問目前所在地",
            message="這裡是什麼地方？我應該觀察什麼？",
            target_npc_id=target_npc_id,
        ),
        PlayerChoice(
            choice_id="ask_for_task",
            label="詢問能幫什麼忙",
            message="有什麼需要我幫忙的任務？",
            target_npc_id=target_npc_id,
        ),
        contextual,
    ]


def _travel_choices(scene_id: str) -> list[PlayerChoice]:
    return [
        PlayerChoice(
            choice_id=f"travel_to_{destination.scene_id}",
            label=f"前往{destination.display_name}",
            message=f"我前往{destination.display_name}。",
            action_mode=ActionMode.MOVEMENT,
            destination_scene_id=destination.scene_id,
        )
        for destination in travel_destinations(scene_id)
    ]
