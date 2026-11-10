from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class StoryPhase(str, Enum):
    """故事推進階段與特殊狀態"""
    ACT1_APPROACHING = "Act1_Approaching"  # 階段一：接近期
    ACT2_MIDTERM = "Act2_Midterm"          # 階段二：中期
    ACT3_FREEDOM = "Act3_Freedom"          # 階段三：自由期
    ACT4_ENDING = "Act4_Ending"            # 階段四：結局期
    USURP_COUNTDOWN = "UsurpCountdown"     # 特殊狀態：篡夢倒數


class InventoryItem(BaseModel):
    """道具模型"""
    item_id: str
    name: str = ""
    description: str = ""


class SceneState(BaseModel):
    """場景狀態"""
    scene_id: str
    visited: bool = False


class NPCState(BaseModel):
    """NPC 狀態模型：簡化為單一 relation 關係值"""
    npc_id: str
    name: str = ""
    relation: int = Field(default=30, ge=0, le=100)  # 關係值 (0 ~ 100)
    met: bool = False  # 是否已相遇


class PlayerState(BaseModel):
    """玩家狀態模型"""
    player_id: str = "player_01"
    name: str = "主角"
    inventory: List[str] = Field(default_factory=list)


class GameState(BaseModel):
    """遊戲核心狀態模型 (草案 v3 規格)[cite: 53, 55]"""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    state_version: int = Field(default=1, ge=1)
    turn_count: int = 0                  # 總遊戲回合計數
    phase_turns: int = 0                 # 當前階段已消耗的回合數
    current_scene_id: str = "fissure"    # 當前場景 ID (初始在屏障裂隙)
    
    # 流程與階段控制[cite: 53, 56, 57, 59]
    story_phase: StoryPhase = StoryPhase.ACT1_APPROACHING
    usurp_countdown_turns: int = 3       # 篡夢倒數剩餘回合數 (預設 3)
    warning_triggered: bool = False      # 警告事件 W 是否已觸發
    
    # 草案 v3 三大核心結局數值[cite: 53, 55]
    axis: int = Field(default=0, ge=-100, le=100)    # 主軸傾向值 (-100 ~ +100)
    usurp: int = Field(default=0, ge=0, le=100)       # 篡奪值 (0 ~ 100)
    truth_level: int = Field(default=0, ge=0, le=3)   # 真相度 (0 ~ 3)
    
    # NPC 關係狀態集合 (預設初始值：安德烈 20, 維達利亞 30, 門梅司文托 30)
    npc_states: Dict[str, NPCState] = Field(
        default_factory=lambda: {
            "andre": NPCState(npc_id="andre", name="安德烈", relation=20),
            "vidalia": NPCState(npc_id="vidalia", name="維達利亞", relation=30),
            "menmesvento": NPCState(npc_id="menmesvento", name="門梅司文托", relation=30)
        }
    )
    
    # 關鍵劇情旗標 (Flags)
    flags: Dict[str, Any] = Field(
        default_factory=lambda: {
            "elder_cooperation": False,   # 長老協力
            "library_path": False,        # 圖書館路徑
            "fissure_map": False,         # 裂隙地圖
            "has_dust_token": False,      # 持有塵歸令
            "is_transformed": False,      # 已轉化
        }
    )
    
    player: PlayerState = Field(default_factory=PlayerState)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
