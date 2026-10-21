"""Schemas describing the current, serializable game state."""

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class InventoryItem(BaseModel):
    """One item currently held by the player."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    quantity: int = Field(default=1, ge=0)


class PlayerState(BaseModel):
    """State that can change as a result of validated player actions."""

    model_config = ConfigDict(extra="forbid")

    player_id: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=100)
    current_scene_id: str = Field(..., min_length=1, max_length=100)
    health: int = Field(default=100, ge=0, le=100)
    inventory: list[InventoryItem] = Field(default_factory=list)
    flags: dict[str, Any] = Field(default_factory=dict)


class NPCState(BaseModel):
    """Current state of an NPC relevant to story generation and rules."""

    model_config = ConfigDict(extra="forbid")

    npc_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=100)
    current_scene_id: str = Field(..., min_length=1, max_length=100)
    affection: int = Field(default=0, ge=-100, le=100)
    trust: int = Field(default=0, ge=-100, le=100)
    emotion: str = Field(default="neutral", min_length=1, max_length=50)
    flags: dict[str, Any] = Field(default_factory=dict)


class SceneState(BaseModel):
    """The currently active scene and its immediately available transitions."""

    model_config = ConfigDict(extra="forbid")

    scene_id: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=200)
    available_exit_ids: list[str] = Field(default_factory=list)
    active_npc_ids: list[str] = Field(default_factory=list)
    flags: dict[str, Any] = Field(default_factory=dict)


class GameState(BaseModel):
    """Complete state snapshot exchanged between the orchestrator and API."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(..., min_length=1, max_length=100)
    turn_number: int = Field(default=0, ge=0)
    player: PlayerState
    npcs: dict[str, NPCState] = Field(default_factory=dict)
    current_scene: SceneState
    world_flags: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

