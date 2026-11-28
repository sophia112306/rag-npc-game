"""Request contract for the narrative AI (規格 v3「系統總覽」：判讀玩家發言，提出數值變化).

The response reuses ``NarrativeAIResponse`` / ``DeltaPayload`` from ``api_response``.
Unlike NPC requests, the narrative AI may read the numeric state, because the
backend still clamps every value it proposes (StateRules.apply_dialogue_delta).
"""

from typing import Dict

from pydantic import BaseModel, ConfigDict, Field

from .game_state import StoryPhase


# 規格 v3「主軸的發言判讀」的立場類別與方向（-1 偏守夢、+1 偏醒夢）。
# 敘事 AI 從這份清單選一個；「同一立場 3 回合內只計一次」以類別判斷。
AXIS_STANCES: Dict[str, int] = {
    "留戀": -1,
    "尋求安寧": -1,
    "承諾陪伴": -1,
    "肯定永生或輪迴": -1,
    "保存記憶": -1,
    "維持現狀": -1,
    "探討死亡的意義": 1,
    "指出長生的虛妄": 1,
    "支持門梅司文托": 1,
    "主張打破循環": 1,
}


def valid_axis_stance(stance: object, axis_delta: int) -> str | None:
    """類別在清單內、且方向與主軸變化一致才採用；否則視為沒有類別。"""

    if not isinstance(stance, str) or not axis_delta:
        return None
    direction = AXIS_STANCES.get(stance.strip())
    if direction is None or (direction > 0) != (axis_delta > 0):
        return None
    return stance.strip()


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
    legal_event_labels: list[str] = Field(default_factory=list)
