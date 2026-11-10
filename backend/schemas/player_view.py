"""Player-visible projections derived from authoritative internal state."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

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


class PlayerViewState(BaseModel):
    """State projection safe to return through player-facing APIs."""

    model_config = ConfigDict(extra="ignore")

    session_id: str
    state_version: int
    turn_count: int
    current_scene_id: str
    player: PlayerIdentityView
    npc_states: dict[str, NPCPublicStateView]
    created_at: datetime
    updated_at: datetime


def project_player_view(state: GameState) -> PlayerViewState:
    """Remove author-only facts, secret flags, and private NPC state."""

    return PlayerViewState(
        session_id=state.session_id,
        state_version=state.state_version,
        turn_count=state.turn_count,
        current_scene_id=state.current_scene_id,
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
