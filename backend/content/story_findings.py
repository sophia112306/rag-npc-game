"""Readable evidence derived only from established, player-visible choices."""

from dataclasses import dataclass

from backend.content.reveal_policy import is_demo_first_stage, public_clue_ids, public_story_text
from backend.content.scenes import require_scene
from backend.schemas.game_state import GameState


@dataclass(frozen=True)
class PublicFinding:
    clue_id: str
    title: str
    summary: str
    scene_id: str
    scene_name: str
    source_npc_id: str | None
    kind: str
    visual_signal: str | None


def public_findings(state: GameState) -> list[PublicFinding]:
    # Lazy import avoids the schemas package's re-export cycle.
    from backend.content.demo_story import DEMO_STORY_CHOICES

    visible = public_clue_ids(state.story_progress.public_clue_ids, demo_act1=is_demo_first_stage(state))
    completed = set(state.story_progress.completed_choice_ids)
    result = []
    for clue_id in visible:
        source = next((choice for choice in DEMO_STORY_CHOICES
                       if choice.choice_id in completed and clue_id in choice.reveal_clue_ids), None)
        if source is None:
            continue  # An unknown ID is not permission to invent its contents.
        result.append(PublicFinding(
            clue_id=clue_id, title=source.label,
            summary=public_story_text(source.response_text),
            scene_id=source.source_scene_id,
            scene_name=require_scene(source.source_scene_id).display_name,
            source_npc_id=source.target_npc_id,
            kind="conversation" if source.target_npc_id else "investigation",
            visual_signal=source.visual_signal,
        ))
    return result


def finding_report(state: GameState) -> str:
    findings = public_findings(state)
    if not findings:
        return "目前還沒有已記錄、可回報的調查線索。"
    return "\n".join(f"{finding.scene_name}｜{finding.summary}" for finding in findings)
