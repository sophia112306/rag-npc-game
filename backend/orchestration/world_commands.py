"""Explicit scene commands converted to the same validated proposal pipeline."""

from hashlib import sha256
import re

from backend.content.world_scenes import default_config
from backend.schemas.game_state import GameState
from backend.schemas.player_action import PlayerAction
from backend.schemas.story import ConfigureSceneOperation, EventProposal, StoryProposal
from backend.schemas.world_scene import WorldSceneConfig


class UnsupportedWorldCommand(ValueError):
    pass


def _number(text: str) -> int:
    if text.isdigit():
        return int(text)
    digits = {
        "零": 0,
        "一": 1,
        "二": 2,
        "兩": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if "百" in text or "千" in text or "萬" in text:
        return 1000
    if "十" in text:
        a, b = text.split("十", 1)
        return digits.get(a, 1) * 10 + digits.get(b, 0)
    return digits.get(text, 1)


def build_world_command_proposal(
    action: PlayerAction, state: GameState
) -> StoryProposal:
    text = action.message.strip().lower()
    if re.search(r"[-−]\s*\d", text):
        raise UnsupportedWorldCommand("物件數量不可為負數。")
    current = state.world_scenes.get(state.current_scene_id) or default_config(
        state.current_scene_id
    )
    changes: dict[str, object] = {}
    if any(word in text for word in ("晴天", "放晴", "晴朗", "clear")):
        changes["weather"] = "clear"
    elif any(word in text for word in ("下雨", "雨天", "雨林", "rain")):
        changes["weather"] = "rain"
    elif any(word in text for word in ("沙塵", "沙暴", "dust")):
        changes["weather"] = "dust"
    elif any(word in text for word in ("霧", "mist", "fog")):
        changes["weather"] = "mist"
    for value, words in (
        ("day", ("白天", "日間", "清晨", "day")),
        ("dusk", ("黃昏", "夕陽", "傍晚", "dusk")),
        ("night", ("夜晚", "夜間", "晚上", "night")),
    ):
        if any(word in text for word in words):
            changes["time_of_day"] = value
    for value, words in (
        ("rolling", ("平緩", "草地", "丘陵")),
        ("dunes", ("沙丘", "沙地")),
        ("rocky", ("岩地", "岩石地形", "岩原")),
    ):
        if any(word in text for word in words):
            changes["terrain"] = value
    for key, pattern, limit in (
        ("tree_count", r"樹木|樹|trees?", 48),
        ("runestone_count", r"符石|石碑|runestones?", 12),
        ("altar_count", r"祭壇|altars?", 3),
    ):
        match = re.search(
            r"([0-9零一二兩三四五六七八九十百千萬]+)\s*(?:個|棵|座|根)?\s*(?:"
            + pattern
            + r")",
            text,
        )
        if match:
            count = _number(match.group(1))
            if count > limit:
                raise UnsupportedWorldCommand(
                    f"單場景最多 {limit} 個此類物件，請降低數量。"
                )
            changes[key] = count
        elif re.search(
            r"(?:移除|清除|刪除|不要|remove)\s*(?:所有|全部)?\s*(?:" + pattern + r")",
            text,
        ):
            changes[key] = 0
    if not changes and not any(
        word in text for word in ("重新生成", "重新佈置", "重排", "regenerate")
    ):
        raise UnsupportedWorldCommand(
            "可調整天氣、日夜、地形與樹木／符石／祭壇數量，例如：生成 6 個符石，夜晚並起霧。"
        )
    changes["revision"] = current.revision + 1
    if any(key.endswith("_count") for key in changes) or any(
        word in text for word in ("重新生成", "重新佈置", "重排", "regenerate")
    ):
        changes["seed"] = int(
            sha256(str(action.action_id).encode()).hexdigest()[:7], 16
        )
    config = WorldSceneConfig.model_validate({**current.model_dump(), **changes})
    return StoryProposal(
        session_id=state.session_id,
        turn_number=state.turn_count + 1,
        intent_summary="依世界指令重建當前可探索場景",
        event_proposals=[
            EventProposal(
                event_type="scene_reconfigured",
                description="已驗證的場景變化",
                actor_id=state.player.player_id,
                operations=[
                    ConfigureSceneOperation(
                        scene_id=state.current_scene_id, config=config
                    )
                ],
            )
        ],
    )
