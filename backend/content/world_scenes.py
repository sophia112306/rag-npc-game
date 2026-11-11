"""Deterministic spatial assembly from saved scene settings, not image walls."""

from hashlib import sha256
import math
import random

from backend.content.scenes import require_scene
from backend.schemas.world_scene import WorldObject, WorldSceneConfig, WorldSceneView


def default_config(scene_id: str) -> WorldSceneConfig:
    seed = int(sha256(scene_id.encode()).hexdigest()[:7], 16)
    settings = {
        "minglin": dict(tree_count=9, runestone_count=2),
        "minglin_life_spring": dict(tree_count=14, runestone_count=3, weather="mist"),
        "minglin_rune_grove": dict(
            tree_count=12, runestone_count=8, time_of_day="dusk"
        ),
        "liuchen_valley": dict(
            tree_count=0,
            runestone_count=7,
            altar_count=2,
            terrain="dunes",
            weather="dust",
        ),
        "lieyi_plains": dict(
            tree_count=0,
            runestone_count=5,
            altar_count=3,
            terrain="rocky",
            time_of_day="dusk",
        ),
    }
    require_scene(scene_id)
    return WorldSceneConfig(seed=seed, **settings[scene_id])


def build_world_scene(
    scene_id: str, config: WorldSceneConfig | None = None
) -> WorldSceneView:
    config = config or default_config(scene_id)
    rng = random.Random(config.seed)
    objects: list[WorldObject] = []
    # Keep a wide traversable corridor between spawn and interaction landmark.
    # Props are placed outside it and have spacing so the player cannot spawn inside them.
    # Frame the original sanctuary, leaving its path, engraved dais and lake clear.
    council_trees = [
        (-7.3, 4.6, 11.6), (7.4, 6.3, 12.4), (-10.7, -4.8, 12.8),
        (9.6, -3.4, 10.8), (-8.5, -18, 13), (5.8, -18.5, 12.4),
        (-16, 0, 13.8), (15, -12, 14), (5.3, -24, 16),
    ]
    occupied: list[tuple[float, float, float]] = (
        [(x, z, 2.0) for x, z, _ in council_trees[:config.tree_count]]
        if scene_id == "minglin" else []
    )
    for kind, count, span, base_scale, radius in (
        ("altar", config.altar_count, 16, 3.6, 2.5),
        ("runestone", config.runestone_count, 23, 2.5, 1.4),
        ("tree", config.tree_count, 39, 8.0, 2.0),
    ):
        for index in range(count):
            primary = index == 0 and (
                (
                    kind == "altar"
                    and scene_id in {"minglin_life_spring", "lieyi_plains"}
                )
                or (kind == "runestone" and scene_id == "minglin_rune_grove")
            )
            authored_tree = scene_id == "minglin" and kind == "tree" and index < len(council_trees)
            if authored_tree:
                x, z, authored_scale = council_trees[index]
            elif primary:
                x, z = 0, -6
            else:
                for _ in range(150):
                    x, z = rng.uniform(-span, span), rng.uniform(-span - 10, span - 2)
                    if abs(x) < 4 or math.hypot(x, z - 8) < 7:
                        continue
                    if scene_id == "minglin" and math.hypot(x, z + 8) < 16:
                        continue
                    if all(
                        math.hypot(x - px, z - pz) > radius + pr
                        for px, pz, pr in occupied
                    ):
                        break
                else:
                    continue
            if not authored_tree:
                occupied.append((x, z, radius))
            scale = (
                authored_scale if authored_tree
                else 6.8 if primary and kind == "altar"
                else round(base_scale * rng.uniform(0.8, 1.25), 3)
            )
            objects.append(
                WorldObject(
                    kind=kind,
                    object_id=f"{kind}-{index}",
                    x=round(x, 3),
                    z=round(z, 3),
                    scale=scale,
                    yaw=round(rng.uniform(0, math.tau), 3),
                )
            )

    npc = {"minglin": "vidalia", "liuchen_valley": "menmesvento"}.get(scene_id)
    label = {
        "minglin": "與維達利亞交談",
        "minglin_life_spring": "調查泉眼",
        "minglin_rune_grove": "調查符石",
        "liuchen_valley": "與門梅司文托交談",
        "lieyi_plains": "調查中央聖火",
    }[scene_id]
    return WorldSceneView(
        scene_id=scene_id,
        config=config,
        objects=objects,
        npc_id=npc,
        interaction_label=label,
        interaction_z=-8 if scene_id == "minglin" else -6,
        water=scene_id == "minglin_life_spring",
        fire=scene_id == "lieyi_plains",
    )
