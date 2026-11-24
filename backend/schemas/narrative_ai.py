"""Request contract for the narrative AI (規格 v3「系統總覽」：判讀玩家發言，提出數值變化).

The response reuses ``NarrativeAIResponse`` / ``DeltaPayload`` from ``api_response``.
Unlike NPC requests, the narrative AI may read the numeric state, because the
backend still clamps every value it proposes (StateRules.apply_dialogue_delta).
"""

from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from .game_state import StoryPhase


class NarrativeAIRequest(BaseModel):
    """One player utterance plus the state the narrative AI needs to judge it."""

    model_config = ConfigDict(extra="forbid")

    player_message: str = Field(..., min_length=1, max_length=2_000)
    target_npc_id: str | None = Field(default=None, max_length=100)
    target_npc_name: str | None = Field(default=None, max_length=100)
    scene_id: str = Field(..., min_length=1, max_length=100)
    scene_name: str = Field(..., min_length=1, max_length=100)
    story_phase: StoryPhase
    axis: int = Field(..., ge=-100, le=100)
    usurp: int = Field(..., ge=0, le=100)
    truth_level: int = Field(..., ge=0, le=3)
    relations: Dict[str, int] = Field(default_factory=dict)
