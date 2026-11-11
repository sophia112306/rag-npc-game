"""Public clue names that do not disclose later story revelations.

Older demo sessions may still contain clue IDs from the first draft. Normalize
those IDs at player and image-provider boundaries without changing saved history.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.schemas.game_state import GameState


LEGACY_PUBLIC_CLUE_ALIASES: dict[str, str] = {
    "spring_stopped_after_first_invasion": "spring_stopped_expanding",
    "factions_seek_player": "factions_notice_anomaly",
    "fire_elder_interest": "elders_near_spring",
    "mummy_memory_motive": "mummies_value_names",
    "fire_elder_control_motive": "elders_surveyed_fire",
}

LEGACY_CHAPTER_TITLES: dict[str, str] = {
    "Demo 完成：長老的企圖": "Demo 完成：長老的行蹤",
    "裂隙地圖": "流塵谷的路標",
}

LEGACY_DEMO_STORY_TEXT: dict[str, str] = {
    "符石路徑在腳下崩解，你借助地圖標出的地理優勢甩開封閉路線，進入流塵谷。": (
        "符石路徑在腳下崩解，你循著先前記下的風沙方向穿過裂隙，進入流塵谷。"
    ),
}

REVISED_DEMO_CHOICE_IDS = frozenset(
    {
        "ask_location",
        "ask_about_factions",
        "ask_about_fire_elder",
        "ask_about_mummies",
        "question_fire_elder_motive",
        "listen_to_forgotten_names",
        "trace_dust_runes",
    }
)


def is_demo_first_stage(state: GameState) -> bool:
    from backend.schemas.game_state import StoryPhase

    return (
        state.story_phase == StoryPhase.ACT1_APPROACHING
        and state.story_progress.mode == "demo_fallback"
    )


def public_clue_ids(clue_ids: Iterable[str], *, demo_act1: bool = False) -> list[str]:
    """Keep existing saves readable while exposing only first-act-safe IDs."""

    aliases = LEGACY_PUBLIC_CLUE_ALIASES.copy()
    if demo_act1:
        aliases["fissure_map"] = "dust_route_trace"
    return list(dict.fromkeys(aliases.get(clue, clue) for clue in clue_ids))


def normalize_legacy_demo_state(state: GameState) -> GameState:
    """Remove a map granted by an old first-stage demo route, not by E2-3."""

    # Older quest travel changed location without advancing the story node.
    # Repair only arrival alignment; do not grant clues, flags or extra turns.
    arrival = {
        "minglin_life_spring": ("life_spring_arrival", "沉默的泉眼"),
        "minglin_rune_grove": ("rune_grove_arrival", "失序的符石"),
    }.get(state.current_scene_id)
    if arrival and state.story_progress.node_id in {
        "minglin_arrival", "minglin_orientation", "minglin_briefed"
    }:
        state.story_progress.node_id, state.story_progress.chapter_title = arrival
    if (
        is_demo_first_stage(state)
        and "fissure_map" in state.story_progress.public_clue_ids
        and any(
            choice_id in state.story_progress.completed_choice_ids
            for choice_id in ("study_spring_echo", "trace_dust_runes")
        )
    ):
        state.story_progress.public_clue_ids = public_clue_ids(
            state.story_progress.public_clue_ids, demo_act1=True
        )
        state.flags["fissure_map"] = False
    return state


def public_chapter_title(title: str) -> str:
    """Avoid replaying a premature conclusion from an older saved demo."""

    return LEGACY_CHAPTER_TITLES.get(title, title)


def public_story_text(text: str) -> str:
    """Keep old first-stage replay text within the current public reveal boundary."""

    for old, current in {**LEGACY_CHAPTER_TITLES, **LEGACY_DEMO_STORY_TEXT}.items():
        text = text.replace(old, current)
    return text
