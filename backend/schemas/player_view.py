"""Player-visible projections derived from authoritative internal state."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from backend.content.reveal_policy import is_demo_first_stage, public_chapter_title, public_clue_ids
from backend.content.scenes import SceneVisualProfile, require_scene
from backend.content.world_scenes import build_world_scene
from backend.schemas.world_scene import WorldSceneView

from .game_state import GameState


class PlayerIdentityView(BaseModel):
    """Safe player fields that may be rendered by the client."""

    model_config = ConfigDict(extra="ignore")

    player_id: str
    name: str
    inventory: list[str]


class NPCPublicStateView(BaseModel):
    """Observable NPC state without private goals, memory, or relationship scores."""

    model_config = ConfigDict(extra="ignore")

    npc_id: str
    name: str
    met: bool


class PlayerSceneView(BaseModel):
    """Public scene metadata needed by both the 2D and 3D clients."""

    model_config = ConfigDict(extra="forbid")

    scene_id: str
    region_name: str
    display_name: str
    subtitle: str
    description: str
    background_url: str
    horizon_url: str
    visual_profile: SceneVisualProfile
    canon_status: Literal["confirmed", "provisional"]


class PlayerStoryProgressView(BaseModel):
    """Only story progress that has already been revealed to the player."""

    model_config = ConfigDict(extra="forbid")

    arc_id: str
    node_id: str
    chapter_title: str
    mode: Literal["demo_fallback"]
    public_clue_ids: list[str]


class PlayerViewState(BaseModel):
    """State projection safe to return through player-facing APIs."""

    model_config = ConfigDict(extra="ignore")

    session_id: str
    state_version: int
    turn_count: int
    current_scene_id: str
    current_scene: PlayerSceneView
    story_progress: PlayerStoryProgressView
    world_scene: WorldSceneView | None = None
    player: PlayerIdentityView
    npc_states: dict[str, NPCPublicStateView]
    created_at: datetime
    updated_at: datetime


def project_player_view(state: GameState) -> PlayerViewState:
    """Remove author-only facts, secret flags, and private NPC state."""

    scene = require_scene(state.current_scene_id)
    return PlayerViewState(
        session_id=state.session_id,
        state_version=state.state_version,
        turn_count=state.turn_count,
        current_scene_id=state.current_scene_id,
        world_scene=build_world_scene(state.current_scene_id, state.world_scenes.get(state.current_scene_id)),
        current_scene=PlayerSceneView(
            scene_id=scene.scene_id,
            region_name=scene.region_name,
            display_name=scene.display_name,
            subtitle=scene.subtitle,
            description=scene.description,
            background_url=scene.background_url,
            horizon_url=scene.horizon_url,
            visual_profile=scene.visual_profile,
            canon_status=scene.canon_status,
        ),
        story_progress=PlayerStoryProgressView(
            arc_id=state.story_progress.arc_id,
            node_id=state.story_progress.node_id,
            chapter_title=public_chapter_title(state.story_progress.chapter_title),
            mode=state.story_progress.mode,
            public_clue_ids=public_clue_ids(
                state.story_progress.public_clue_ids,
                demo_act1=is_demo_first_stage(state),
            ),
        ),
        player=PlayerIdentityView(
            player_id=state.player.player_id,
            name=state.player.name,
            inventory=list(state.player.inventory),
        ),
        npc_states={
            npc_id: NPCPublicStateView(
                npc_id=npc.npc_id,
                name=npc.name,
                met=npc.met,
            )
            for npc_id, npc in state.npc_states.items()
        },
        created_at=state.created_at,
        updated_at=state.updated_at,
    )
