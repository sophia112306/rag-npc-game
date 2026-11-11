"""Turn validated fallback choices into ordinary story proposals."""

from backend.content.demo_story import DemoStoryChoiceDefinition, available_demo_story_choices
from backend.schemas.game_state import GameState
from backend.schemas.player_action import PlayerAction
from backend.schemas.story import (
    AdvanceStoryOperation,
    ChangeSceneOperation,
    DialogueLine,
    EventProposal,
    SpeakerType,
    StoryProposal,
)


def match_typed_story_dialogue(action: PlayerAction, state: GameState) -> DemoStoryChoiceDefinition | None:
    """An exact typed dialogue choice has the same effect as its button.

    No fuzzy intent inference or automatic travel: arbitrary chat still goes
    through the configured planner and cannot unlock an unavailable choice.
    """
    if action.action_mode != "dialogue" or action.destination_scene_id:
        return None
    text = action.message.strip(" \t\n。？！!?")
    return next((choice for choice in available_demo_story_choices(state)
                 if choice.action_mode == "dialogue"
                 and choice.target_npc_id == action.target_npc_id
                 and text in {choice.label.strip("。？！!?"), choice.message.strip("。？！!?")}), None)


def story_choice_action_matches(
    action: PlayerAction,
    choice: DemoStoryChoiceDefinition,
) -> bool:
    """Prevent a client from attaching a valid choice ID to different content."""

    return (
        action.message == choice.message
        and action.target_npc_id == choice.target_npc_id
        and action.action_mode == choice.action_mode
        and action.destination_scene_id == choice.destination_scene_id
    )


def build_demo_story_proposal(
    action: PlayerAction,
    state: GameState,
    choice: DemoStoryChoiceDefinition,
) -> StoryProposal:
    """Create a proposal; the resolver remains authoritative for every effect."""

    operations = [AdvanceStoryOperation(story_choice_id=choice.choice_id)]
    if choice.destination_scene_id:
        operations.append(
            ChangeSceneOperation(
                destination_scene_id=choice.destination_scene_id,
                story_choice_id=choice.choice_id,
            )
        )

    if choice.target_npc_id:
        dialogue = DialogueLine(
            speaker_type=SpeakerType.NPC,
            speaker_id=choice.target_npc_id,
            speaker_name=state.npc_states[choice.target_npc_id].name,
            text=choice.response_text,
            emotion="focused",
        )
    else:
        dialogue = DialogueLine(
            speaker_type=SpeakerType.NARRATOR,
            speaker_name="旁白",
            text=choice.response_text,
        )

    return StoryProposal(
        session_id=action.session_id,
        turn_number=state.turn_count + 1,
        intent_summary=f"Resolve bounded demo story choice '{choice.choice_id}'.",
        proposed_dialogue=[dialogue],
        event_proposals=[
            EventProposal(
                event_type="demo_story_progressed",
                description="Player selected an available bounded story choice.",
                actor_id=state.player.player_id,
                target_id=choice.destination_scene_id or choice.target_npc_id,
                operations=operations,
                witness_ids=[state.player.player_id],
                visible_to_player=True,
            )
        ],
    )
