from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """玩家行動類型分類"""
    DIALOGUE = "dialogue"          # 一般自由對話
    MOVEMENT = "movement"          # 場景移動
    USE_ITEM = "use_item"          # 使用道具 (如塵歸令)
    INSPECT = "inspect"            # 觀察/調查環境
    INTERACTION = "interaction"    # 特殊互動


class ParsedAction(BaseModel):
    """玩家輸入經過意圖解析後的結構"""
    intent: str = Field(description="意圖簡述 (如 ask, move, use_item)")
    actor_id: str = Field(default="player", description="行動者 ID")
    target_ids: List[str] = Field(default_factory=list, description="行動目標 (如 NPC ID、場景或道具)")
    action_type: ActionType = Field(default=ActionType.DIALOGUE, description="行動類型")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="攜帶額外參數")
    confidence: Optional[float] = Field(default=1.0, description="意圖解析信心度")