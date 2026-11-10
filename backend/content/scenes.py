"""Authoritative public scene definitions and allowed travel graph."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SceneDefinition(BaseModel):
    """Immutable scene metadata shared by API projections and rule validation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scene_id: str
    region_name: str
    display_name: str
    subtitle: str
    description: str
    background_url: str
    horizon_url: str
    canon_status: Literal["confirmed", "provisional"]
    allowed_destinations: tuple[str, ...]


SCENES: dict[str, SceneDefinition] = {
    "minglin": SceneDefinition(
        scene_id="minglin",
        region_name="鳴霖",
        display_name="平衡議會",
        subtitle="古林中的議會庭",
        description="維達利亞接見旅人、確認現況的林間議會庭。",
        background_url="/game/forest-council.png",
        horizon_url="/game/forest-eye-backdrop.png",
        canon_status="confirmed",
        allowed_destinations=("minglin_life_spring", "minglin_rune_grove"),
    ),
    "minglin_life_spring": SceneDefinition(
        scene_id="minglin_life_spring",
        region_name="鳴霖",
        display_name="命脈之泉",
        subtitle="古林深處的泉眼",
        description="維達利亞守護的泉眼；場景細節仍待團隊世界觀資料確認。",
        background_url="/game/scenes/minglin-life-spring-v1.png",
        horizon_url="/game/scenes/minglin-life-spring-v1.png",
        canon_status="confirmed",
        allowed_destinations=("minglin",),
    ),
    "minglin_rune_grove": SceneDefinition(
        scene_id="minglin_rune_grove",
        region_name="鳴霖",
        display_name="符石林",
        subtitle="暫定調查地點",
        description="用於驗證動態探索流程的暫定符石場景，尚未列為正式世界設定。",
        background_url="/game/scenes/minglin-rune-grove-v1.png",
        horizon_url="/game/scenes/minglin-rune-grove-v1.png",
        canon_status="provisional",
        allowed_destinations=("minglin",),
    ),
    "liuchen_valley": SceneDefinition(
        scene_id="liuchen_valley",
        region_name="流塵谷",
        display_name="流塵谷",
        subtitle="風沙與裂谷交錯的葬地",
        description="遍布龜裂道路、墓葬遺跡與復生者足跡的風沙峽谷。",
        background_url="/game/scenes/liuchen-valley-v1.png",
        horizon_url="/game/scenes/liuchen-valley-v1.png",
        canon_status="confirmed",
        allowed_destinations=(),
    ),
    "lieyi_plains": SceneDefinition(
        scene_id="lieyi_plains",
        region_name="烈燚原",
        display_name="烈燚原",
        subtitle="暫定火焰場景",
        description="依使用者參考設計建立的火柱、祭壇與熔流原野；正式世界設定仍待團隊確認。",
        background_url="/game/scenes/lieyi-plains-v1.png",
        horizon_url="/game/scenes/lieyi-plains-v1.png",
        canon_status="provisional",
        allowed_destinations=(),
    ),
}


def get_scene(scene_id: str) -> SceneDefinition | None:
    """Return a registered scene without inventing missing metadata."""

    return SCENES.get(scene_id)


def require_scene(scene_id: str) -> SceneDefinition:
    """Return a scene or fail at the internal consistency boundary."""

    scene = get_scene(scene_id)
    if scene is None:
        raise KeyError(f"Unknown scene '{scene_id}'")
    return scene


def travel_destinations(scene_id: str) -> tuple[SceneDefinition, ...]:
    """Return only destinations explicitly connected to the current scene."""

    scene = require_scene(scene_id)
    return tuple(require_scene(destination) for destination in scene.allowed_destinations)


def can_travel(source_scene_id: str, destination_scene_id: str) -> bool:
    """Check a transition against the registered directed scene graph."""

    source = get_scene(source_scene_id)
    return source is not None and destination_scene_id in source.allowed_destinations
