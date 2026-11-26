from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from backend.schemas.world_scene import WorldSceneConfig


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
    inventory: List[str] = Field(default_factory=list)


class PlayerState(BaseModel):
    """玩家狀態模型"""
    player_id: str = "player_01"
    name: str = "主角"
    inventory: List[str] = Field(default_factory=list)


class StoryProgressState(BaseModel):
    """Persisted demo-story position kept separate from author canon."""

    model_config = ConfigDict(extra="forbid")

    arc_id: str = "vita_anomaly_demo_v1"
    node_id: str = "minglin_arrival"
    chapter_title: str = "鳴霖・林間入口"
    mode: Literal["demo_fallback"] = "demo_fallback"
    completed_choice_ids: List[str] = Field(default_factory=list)
    public_clue_ids: List[str] = Field(default_factory=list)
    unlocked_scene_ids: List[str] = Field(
        default_factory=lambda: [
            "minglin",
            "minglin_life_spring",
            "minglin_rune_grove",
        ]
    )


class GameState(BaseModel):
    """遊戲核心狀態模型 (草案 v3 規格)"""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    state_version: int = Field(default=1, ge=1)
    turn_count: int = 0                  # 總遊戲回合計數
    game_status: Literal["active", "completed", "game_over"] = "active"
    final_ending: str | None = None
    phase_turns: int = 0                 # 當前階段已消耗的回合數
    current_scene_id: str = "minglin"    # 當前場景 ID (開場在鳴霖林間入口)
    
    # 流程與階段控制
    story_phase: StoryPhase = StoryPhase.ACT1_APPROACHING
    usurp_countdown_turns: int = 3       # 篡夢倒數剩餘回合數 (預設 3)
    warning_triggered: bool = False      # 警告事件 W 是否已觸發
    warning_cooldown_turns: int = 0      # [新增] W 之後的 5 回合冷卻計數 (大於 0 時 usurp 鎖定上限 89)
    
    # [新增] 草案 v3 防刷分計數器（每階段切換時歸零）
    phase_usurp_dialogue_gain: int = 0   # 本階段靠激怒 NPC 累積的篡奪值 (上限 +10)
    recent_axis_signs: List[int] = Field(default_factory=list)  # 記錄最近 3 回合的主軸傾向符號 (-1, 0, 1)
    recent_axis_stances: List[Optional[str]] = Field(default_factory=list)  # 最近 3 回合的立場類別；有類別時以類別判斷同一立場
    phase_relation_dialogue_gain: Dict[str, int] = Field(
        default_factory=lambda: {"andre": 0, "vidalia": 0, "menmesvento": 0}
    )                                    # 本階段各角色靠對話累積的關係值 (各上限 +40)
    recent_dialogue_messages: List[str] = Field(default_factory=list)  # 最近 3 次對話判讀的玩家原句（正規化後）；同一句話 3 回合內只計一次
    dialogue_counters_phase: Optional[StoryPhase] = None  # phase_*_dialogue_gain 計數器所屬的階段；階段改變時歸零
    
    # 草案 v3 三大核心結局數值
    axis: int = Field(default=0, ge=-100, le=100)    # 主軸傾向值 (-100 ~ +100)
    usurp: int = Field(default=0, ge=0, le=100)       # 篡奪值 (0 ~ 100)
    truth_level: int = Field(default=0, ge=0, le=3)   # 真相度 (0 ~ 3)
    
    # NPC 關係狀態集合；安德烈初始 20，其餘已登錄角色初始 30。
    npc_states: Dict[str, NPCState] = Field(
        default_factory=lambda: {
            "andre": NPCState(npc_id="andre", name="安德烈", relation=20),
            "vidalia": NPCState(npc_id="vidalia", name="維達利亞", relation=30),
            "menmesvento": NPCState(npc_id="menmesvento", name="門梅司文托", relation=30),
            "dasso": NPCState(npc_id="dasso", name="達索", relation=30),
            "seth": NPCState(npc_id="seth", name="塞特", relation=30),
            "syra": NPCState(npc_id="syra", name="希拉", relation=30),
        }
    )
    
    # 關鍵劇情旗標 (Flags)
    flags: Dict[str, Any] = Field(
        default_factory=lambda: {
            "elder_cooperation": False,   # 長老協力
            "library_path": False,        # 圖書館路徑
            "fissure_map": False,         # 裂隙拓印圖（內部 ID 保留 fissure_map）
            "has_dust_token": False,      # 持有塵歸令
            "is_transformed": False,      # 已轉化（相容舊布林判斷）
            "transformed_race": None,     # [新增] 已轉化具體種族 (None / "elf" / "mummy" / "human")
            "placed_runes": [],           # [新增] 已放置觀測符印的地點清單 (最多 3 處，用於拆除)
            "epilogue_flags": {},         # [新增] 尾聲旗標 (記錄 E2-2、E2-3 結果與終局第 1、2 題回答)
        }
    )
    
    player: PlayerState = Field(default_factory=PlayerState)
    story_progress: StoryProgressState = Field(default_factory=StoryProgressState)
    world_scenes: Dict[str, WorldSceneConfig] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
