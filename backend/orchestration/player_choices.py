"""Build player-visible shortcuts from authoritative story and scene data."""

from backend.content.demo_story import available_demo_story_choices
from backend.content.scenes import travel_destinations
from backend.schemas.game_state import GameState
from backend.schemas.player_action import ActionMode, PlayerAction
from backend.schemas.player_choice import PlayerChoice
from backend.schemas.progression import PlayerQuestView


def build_player_choices(
    state: GameState,
    quests: list[PlayerQuestView],
    npc_id: str = "vidalia",
) -> list[PlayerChoice]:
    """Return a small contextual set; movement comes from the scene graph."""

    if npc_id == "andre":
        return [
            PlayerChoice(
                choice_id="andre_ask_anomaly",
                label="詢問林地異象",
                message="你在林地邊緣觀察到什麼異象？",
                target_npc_id="andre",
            ),
            PlayerChoice(
                choice_id="andre_ask_trail",
                label="詢問調查路線",
                message="我可以從哪裡開始調查？",
                target_npc_id="andre",
            ),
        ]

    if npc_id == "menmesvento":
        return [
            PlayerChoice(
                choice_id="menmesvento_ask_names",
                label="詢問流塵谷的名字",
                message="為什麼這裡的人如此重視名字？",
                target_npc_id="menmesvento",
            ),
            PlayerChoice(
                choice_id="menmesvento_ask_record",
                label="詢問手中的古卷",
                message="你在古卷裡記錄什麼？",
                target_npc_id="menmesvento",
            ),
        ]

    story_choices = available_demo_story_choices(state)
    if story_choices and not (
        quests and state.story_progress.node_id == "minglin_arrival"
    ):
        return [choice.to_player_choice() for choice in story_choices]

    travel = _travel_choices(state.current_scene_id)
    dialogue_limit = max(1, 4 - len(travel))
    return [*_dialogue_choices(state, quests)[:dialogue_limit], *travel]


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
