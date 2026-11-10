"""Typed response contracts exposed by the FastAPI layer."""

from uuid import UUID, uuid4
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from .parsed_action import ParsedAction
from .player_view import PlayerViewState
from .story import ResolvedStory


class DeltaPayload(BaseModel):
    """敘事 AI 提出的單回合數值增減 Payload (受程式單回合限制)"""
    axis: int = Field(default=0, ge=-5, le=5, description="主軸增減 (-5 ~ +5)")
    usurp: int = Field(default=0, ge=0, le=2, description="篡奪值增減 (0 ~ +2)")
    relation: Dict[str, int] = Field(
        default_factory=dict,
        description="各 NPC 關係值增減 (單次約 -10 ~ +10)"
    )


class NarrativeAIResponse(BaseModel):
    """敘事 AI 每回合輸出的 JSON 解析結構"""
    scene: str = Field(description="當前場景描述")
    speaker: str = Field(description="當前說話的 NPC 或敘事者 ID")
    delta: DeltaPayload = Field(default_factory=DeltaPayload, description="數值變更 Payload")
    event_done: Optional[str] = Field(default=None, description="觸發完成的事件 ID")
    flags_set: List[str] = Field(default_factory=list, description="欲設定的旗標清單")
    reason: str = Field(default="", description="AI 判讀理由")


class ApiError(BaseModel):
    """Stable error shape for frontend handling and logging."""
    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=500)
    details: dict[str, str] = Field(default_factory=dict)


class GameTurnResponse(BaseModel):
    """Response returned after one player action is processed."""
    model_config = ConfigDict(extra="forbid")

    request_id: UUID = Field(default_factory=uuid4)
    session_id: str = Field(..., min_length=1, max_length=100)
    turn_number: int = Field(..., ge=0)
    parsed_action: ParsedAction
    story: ResolvedStory
    state: PlayerViewState
    narrative: Optional[NarrativeAIResponse] = None
    available_endings: List[str] = Field(default_factory=list, description="當前可選結局清單")
