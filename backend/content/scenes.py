"""Authoritative public scene definitions and allowed travel graph."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class SceneVisualProfile(BaseModel):
    """Public rendering parameters; story routes remain server-authoritative."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    profile_id: str
    clear_color: str
    fog_color: str
    fog_density: float
    ambient_color: str
    ground_color: str
    use_ground_texture: bool
    sky_color: str
    sky_ground_color: str
    sky_intensity: float
    key_light_color: str
    key_light_intensity: float
    accent_light_color: str
    accent_light_intensity: float
    backdrop_emissive_color: str
    surface_color: str
    surface_light_color: str
    surface_dark_color: str
    organic_color: str
    rune_color: str
    rune_emissive_color: str
    liquid_color: str
    liquid_emissive_color: str
    prop_groups: tuple[Literal["forest", "path", "council", "pillars", "spring"], ...]
    show_ground: bool
    show_vidalia: bool


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
    tilemap_url: str
    visual_profile: SceneVisualProfile
    canon_status: Literal["confirmed", "provisional"]
    allowed_destinations: tuple[str, ...]
    map_position: tuple[int, int]


SCENES: dict[str, SceneDefinition] = {
    "minglin": SceneDefinition(
        scene_id="minglin",
        region_name="鳴霖",
        display_name="平衡議會",
        subtitle="古林中的議會庭",
        description="維達利亞接見旅人、確認現況的林間議會庭。",
        background_url="/game/forest-council.png",
        horizon_url="/game/forest-eye-backdrop.png",
        tilemap_url="/game/minglin.tmj",
        visual_profile=SceneVisualProfile(
            profile_id="minglin_council",
            clear_color="#142e38",
            fog_color="#29525c",
            fog_density=0.011,
            ambient_color="#2e3b45",
            ground_color="#b5c2b6",
            use_ground_texture=True,
            sky_color="#d1e5e3",
            sky_ground_color="#2e4038",
            sky_intensity=0.72,
            key_light_color="#c7e3e0",
            key_light_intensity=0.85,
            accent_light_color="#ffe0b0",
            accent_light_intensity=0.26,
            backdrop_emissive_color="#666b66",
            surface_color="#92958a",
            surface_light_color="#aaafa0",
            surface_dark_color="#657970",
            organic_color="#537e65",
            rune_color="#668f88",
            rune_emissive_color="#183d39",
            liquid_color="#2d9297",
            liquid_emissive_color="#1e626c",
            prop_groups=(),
            show_ground=False,
            show_vidalia=True,
        ),
        canon_status="confirmed",
        allowed_destinations=("minglin_life_spring", "minglin_rune_grove"),
        map_position=(644, 433),
    ),
    "minglin_life_spring": SceneDefinition(
        scene_id="minglin_life_spring",
        region_name="鳴霖",
        display_name="命脈之泉",
        subtitle="古林深處的泉眼",
        description="林間泉水匯聚於古老石岸，水面的痕跡仍待查探。",
        background_url="/game/scenes/minglin-life-spring-v1.png",
        horizon_url="/game/scenes/minglin-life-spring-v1.png",
        tilemap_url="/game/life-spring.tmj",
        visual_profile=SceneVisualProfile(
            profile_id="minglin_life_spring",
            clear_color="#102b31",
            fog_color="#236b70",
            fog_density=0.018,
            ambient_color="#244849",
            ground_color="#739884",
            use_ground_texture=True,
            sky_color="#b8eee8",
            sky_ground_color="#183f3a",
            sky_intensity=0.86,
            key_light_color="#a9f0e8",
            key_light_intensity=0.78,
            accent_light_color="#8fffe6",
            accent_light_intensity=0.4,
            backdrop_emissive_color="#4d7771",
            surface_color="#748d83",
            surface_light_color="#a5bdb0",
            surface_dark_color="#405f58",
            organic_color="#39775d",
            rune_color="#65c7b5",
            rune_emissive_color="#17695f",
            liquid_color="#25b4bd",
            liquid_emissive_color="#147b8b",
            # The generated background is a complete perspective illustration.
            # Primitive forest/spring meshes break that perspective and are kept
            # disabled until matching scene-specific GLB assets are available.
            prop_groups=(),
            show_ground=False,
            show_vidalia=False,
        ),
        canon_status="confirmed",
        allowed_destinations=("minglin",),
        map_position=(276, 188),
    ),
    "minglin_rune_grove": SceneDefinition(
        scene_id="minglin_rune_grove",
        region_name="鳴霖",
        display_name="符石林",
        subtitle="古樹與符痕交錯的林地",
        description="符石散落在古樹之間，微光沿石面紋路流動。",
        background_url="/game/scenes/minglin-rune-grove-v1.png",
        horizon_url="/game/scenes/minglin-rune-grove-v1.png",
        tilemap_url="/game/rune-grove.tmj",
        visual_profile=SceneVisualProfile(
            profile_id="minglin_rune_grove",
            clear_color="#141c2c",
            fog_color="#344a63",
            fog_density=0.016,
            ambient_color="#31364b",
            ground_color="#7b817b",
            use_ground_texture=True,
            sky_color="#c3d6eb",
            sky_ground_color="#242e39",
            sky_intensity=0.67,
            key_light_color="#abc7e6",
            key_light_intensity=0.74,
            accent_light_color="#b890ff",
            accent_light_intensity=0.48,
            backdrop_emissive_color="#50566b",
            surface_color="#77778a",
            surface_light_color="#a7a3b4",
            surface_dark_color="#4d4d65",
            organic_color="#4f6b60",
            rune_color="#9b82d0",
            rune_emissive_color="#4a267c",
            liquid_color="#415f83",
            liquid_emissive_color="#263a63",
            # Do not layer the council prototype's primitive props over this
            # complete illustration; it creates visible scale/perspective seams.
            prop_groups=(),
            show_ground=False,
            show_vidalia=False,
        ),
        canon_status="provisional",
        allowed_destinations=("minglin",),
        map_position=(287, 663),
    ),
    "liuchen_valley": SceneDefinition(
        scene_id="liuchen_valley",
        region_name="流塵谷",
        display_name="流塵谷",
        subtitle="風沙與裂谷交錯的葬地",
        description="遍布龜裂道路、墓葬遺跡與復生者足跡的風沙峽谷。",
        background_url="/game/scenes/liuchen-valley-v1.png",
        horizon_url="/game/scenes/liuchen-valley-v1.png",
        tilemap_url="/game/liuchen.tmj",
        visual_profile=SceneVisualProfile(
            profile_id="liuchen_dust_valley",
            clear_color="#5b4430",
            fog_color="#a68158",
            fog_density=0.024,
            ambient_color="#5d4938",
            ground_color="#b88a54",
            use_ground_texture=False,
            sky_color="#d8b986",
            sky_ground_color="#63462f",
            sky_intensity=0.9,
            key_light_color="#f1c88d",
            key_light_intensity=1.05,
            accent_light_color="#c0834c",
            accent_light_intensity=0.2,
            backdrop_emissive_color="#8a704f",
            surface_color="#8c6d4d",
            surface_light_color="#b29167",
            surface_dark_color="#564231",
            organic_color="#594737",
            rune_color="#947957",
            rune_emissive_color="#44301e",
            liquid_color="#70604d",
            liquid_emissive_color="#37291f",
            prop_groups=(),
            show_ground=False,
            show_vidalia=False,
        ),
        canon_status="confirmed",
        allowed_destinations=(),
        map_position=(1360, 307),
    ),
    "lieyi_plains": SceneDefinition(
        scene_id="lieyi_plains",
        region_name="烈燚原",
        display_name="烈燚原",
        subtitle="聖火映照的熔流原野",
        description="聖火映照著玄武岩祭壇，冷卻的石路穿過熔流。",
        background_url="/game/scenes/lieyi-plains-v1.png",
        horizon_url="/game/scenes/lieyi-plains-v1.png",
        tilemap_url="/game/lieyi-plains.tmj",
        visual_profile=SceneVisualProfile(
            profile_id="lieyi_sacred_fire",
            clear_color="#33110d",
            fog_color="#7f2917",
            fog_density=0.02,
            ambient_color="#49201c",
            ground_color="#271417",
            use_ground_texture=False,
            sky_color="#ffb044",
            sky_ground_color="#431418",
            sky_intensity=0.94,
            key_light_color="#ff8a33",
            key_light_intensity=1.18,
            accent_light_color="#ffd45c",
            accent_light_intensity=0.72,
            backdrop_emissive_color="#a23d19",
            surface_color="#50302e",
            surface_light_color="#74413a",
            surface_dark_color="#241619",
            organic_color="#6e321d",
            rune_color="#f47b20",
            rune_emissive_color="#a8370c",
            liquid_color="#ff681c",
            liquid_emissive_color="#c92f08",
            prop_groups=(),
            show_ground=False,
            show_vidalia=False,
        ),
        canon_status="provisional",
        allowed_destinations=(),
        map_position=(1418, 584),
    ),
}

SCENES["border_ruins"] = SceneDefinition(
    scene_id="border_ruins",
    region_name="邊境廢墟",
    display_name="邊境廢墟",
    subtitle="流塵谷與人族領地之間",
    description="殘破石門連接風沙荒原與人族領地，兩名旅人在路口停留。",
    background_url="/game/scenes/border-ruins-v1.png",
    horizon_url="/game/scenes/border-ruins-v1.png",
    tilemap_url="/game/border-ruins.tmj",
    visual_profile=SCENES["liuchen_valley"].visual_profile.model_copy(
        update={"profile_id": "border_ruins", "fog_density": 0.019}
    ),
    canon_status="provisional",
    allowed_destinations=(),
    map_position=(1395, 452),
)


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
