"""Player-visible projections derived from authoritative internal state."""

from datetime import datetime
from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.content.reveal_policy import is_demo_first_stage, public_chapter_title, public_clue_ids
from backend.content.scenes import SCENES, SceneVisualProfile, require_scene
from backend.content.world_scenes import build_world_scene
from backend.schemas.world_scene import WorldDiscovery, WorldSceneView

from .game_state import GameState
from .player_choice import PlayerChoice


class PlayerMapSceneView(BaseModel):
    scene_id: str
    display_name: str
    region_name: str
    map_x: int
    map_y: int
    background_url: str
    current: bool
    unlocked: bool
    travel_choice: PlayerChoice | None = None
    hint: str


class PlayerNavigationView(BaseModel):
    objective: str
    scenes: list[PlayerMapSceneView]


def project_navigation(state: GameState) -> PlayerNavigationView:
    """Public map and exact validated actions; no private rules or memory."""
    # Imported at projection time because schemas are re-exported by __init__.
    from backend.orchestration.player_choices import build_player_choices

    choices = build_player_choices(state, [])
    routes = {c.destination_scene_id: c for c in choices if c.destination_scene_id}
    investigations = [c for c in choices if c.action_mode == "interaction"]
    if state.story_progress.node_id == "demo_complete":
        objective = (
            "兩條調查已完成，可前往邊境廢墟預覽第二幕；正式章節尚未開放。"
            if "border_ruins" in routes else
            "這條調查已完成。可探索另一條路線；正式後續章節尚未開放。"
        )
    elif investigations:
        objective = "下一步：" + "／".join(c.label for c in investigations[:2]) + "。走近地標按 E 調查。"
    elif routes:
        names = "／".join(require_scene(scene_id).display_name for scene_id in routes)
        objective = f"下一步：前往{names}，繼續調查。"
    else:
        labels = "／".join(choice.label for choice in choices[:2])
        objective = f"下一步：{labels}。" if labels else "走近人物或地標，查看目前可做的事。"
    scenes = []
    for scene in SCENES.values():
        current = scene.scene_id == state.current_scene_id
        unlocked = current or scene.scene_id in state.story_progress.unlocked_scene_ids
        route = routes.get(scene.scene_id)
        hint = (
            "你目前在這裡。" if current else
            "這條路線現在可以出發。" if route else
            "先在命脈之泉或符石林調查線索。" if not unlocked else
            "目前沒有直達路線，請依當前調查繼續探索。"
        )
        scenes.append(PlayerMapSceneView(
            scene_id=scene.scene_id, display_name=scene.display_name,
            region_name=scene.region_name, map_x=scene.map_position[0], map_y=scene.map_position[1],
            background_url=scene.background_url, current=current, unlocked=unlocked,
            travel_choice=route, hint=hint,
        ))
    return PlayerNavigationView(objective=objective, scenes=scenes)


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
    tilemap_url: str = ""
    visual_profile: SceneVisualProfile
    canon_status: Literal["confirmed", "provisional"]

    @model_validator(mode="after")
    def restore_legacy_tilemap(self):
        # Persisted responses from before the 2D map contract have no URL.
        if not self.tilemap_url:
            self.tilemap_url = require_scene(self.scene_id).tilemap_url
        return self


class PlayerFindingView(BaseModel):
    clue_id: str
    title: str
    summary: str
    scene_id: str
    scene_name: str
    source_npc_id: str | None
    kind: Literal["conversation", "investigation"]
    visual_signal: Literal["ember", "dust"] | None = None


class PlayerStoryProgressView(BaseModel):
    """Only story progress that has already been revealed to the player."""

    model_config = ConfigDict(extra="forbid")

    arc_id: str
    node_id: str
    chapter_title: str
    mode: Literal["demo_fallback"]
    public_clue_ids: list[str]
    findings: list[PlayerFindingView] = Field(default_factory=list)


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
    navigation: PlayerNavigationView | None = None
    player: PlayerIdentityView
    npc_states: dict[str, NPCPublicStateView]
    created_at: datetime
    updated_at: datetime


def project_player_view(state: GameState) -> PlayerViewState:
    """Remove author-only facts, secret flags, and private NPC state."""

    from backend.content.story_findings import public_findings

    scene = require_scene(state.current_scene_id)
    findings = public_findings(state)
    world = build_world_scene(state.current_scene_id, state.world_scenes.get(state.current_scene_id))
    latest = next((finding for finding in reversed(findings)
                   if finding.scene_id == state.current_scene_id and finding.visual_signal), None)
    if latest:
        world.discovery = WorldDiscovery(clue_id=latest.clue_id, label=latest.title, signal=latest.visual_signal)
    return PlayerViewState(
        session_id=state.session_id,
        state_version=state.state_version,
        turn_count=state.turn_count,
        current_scene_id=state.current_scene_id,
        navigation=project_navigation(state),
        world_scene=world,
        current_scene=PlayerSceneView(
            scene_id=scene.scene_id,
            region_name=scene.region_name,
            display_name=scene.display_name,
            subtitle=scene.subtitle,
            description=scene.description,
            background_url=scene.background_url,
            horizon_url=scene.horizon_url,
            tilemap_url=scene.tilemap_url,
            visual_profile=scene.visual_profile,
            canon_status=scene.canon_status,
        ),
        story_progress=PlayerStoryProgressView(
            arc_id=state.story_progress.arc_id,
            node_id=state.story_progress.node_id,
            chapter_title=public_chapter_title(state.story_progress.chapter_title),
            mode=state.story_progress.mode,
            findings=[PlayerFindingView(**asdict(finding)) for finding in findings],
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
