"""Turn validated fallback choices into ordinary story proposals."""

from backend.content.characters import CHARACTER_PROFILES
from backend.content.demo_story import DemoStoryChoiceDefinition, available_demo_story_choices, available_npc_dialogue_choices
from backend.content.story_findings import finding_report
from backend.orchestration.input_classification import normalize_authored_choice_text
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
    text = normalize_authored_choice_text(action.message)
    choices = (*available_demo_story_choices(state), *available_npc_dialogue_choices(state, action.target_npc_id or ""))
    exact_choice = next((choice for choice in choices
                 if choice.action_mode == "dialogue"
                 and choice.target_npc_id == action.target_npc_id
                 and text in {
                     normalize_authored_choice_text(choice.label),
                     normalize_authored_choice_text(choice.message),
                 }), None)
    if exact_choice:
        return exact_choice

    # During the two authored introductions, natural text is still the same
    # story beat as the visible shortcut. This lets the player answer Andre or
    # Vidalia naturally without allowing the turn to skip the opening route.
    opening_choice_ids = {
        ("minglin_arrival", "andre"): "meet_andre",
        ("minglin_council", "vidalia"): "meet_vidalia",
        ("minglin_orientation", "vidalia"): "ask_for_task",
    }
    choice_id = opening_choice_ids.get((state.story_progress.node_id, action.target_npc_id or ""))
    return next((choice for choice in choices if choice.choice_id == choice_id), None)


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

    speaker_npc_id = choice.speaker_npc_id or (
        choice.target_npc_id if not choice.narrate_response else None
    )
    if speaker_npc_id:
        dialogue = DialogueLine(
            speaker_type=SpeakerType.NPC,
            speaker_id=speaker_npc_id,
            speaker_name=CHARACTER_PROFILES[speaker_npc_id].name,
            text=(f"我記下了你這次的回報：\n{finding_report(state)}\n我們先保留這些紀錄，再比對另一條路線。"
                  if choice.choice_id == "review_demo_findings" else choice.response_text),
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
                witness_ids=list(dict.fromkeys([state.player.player_id, *([choice.target_npc_id] if choice.target_npc_id else []), *choice.witness_npc_ids])),
                visible_to_player=True,
            )
        ],
    )
