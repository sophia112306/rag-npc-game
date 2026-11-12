"""Each fixed scene image has reachable, scene-specific 2D interactions."""

from collections import deque
import json
from pathlib import Path

from backend.content.scenes import SCENES
from backend.content.characters import NPC_SCENES, npc_is_present
from backend.schemas.game_state import GameState
from backend.schemas.player_view import PlayerSceneView, project_player_view


PUBLIC = Path(__file__).resolve().parents[1] / "frontend/public"


def _contains(polygon, x, y):
    inside = False
    previous = polygon[-1]
    for point in polygon:
        if (point["y"] > y) != (previous["y"] > y):
            crossing = (previous["x"] - point["x"]) * (y - point["y"]) / (previous["y"] - point["y"]) + point["x"]
            if x < crossing:
                inside = not inside
        previous = point
    return inside


def test_all_fixed_images_have_their_own_reachable_map():
    assert len({scene.tilemap_url for scene in SCENES.values()}) == len(SCENES)
    for scene in SCENES.values():
        path = PUBLIC / scene.tilemap_url.lstrip("/")
        document = json.loads(path.read_text())
        layers = {layer["name"]: layer for layer in document["layers"]}
        assert (path.parent / layers["Background"]["image"]).resolve() == (PUBLIC / scene.background_url.lstrip("/")).resolve()
        polygons = [obj["polygon"] for obj in layers["Walkable"]["objects"]]
        actors = layers["Actors"]["objects"]
        assert {actor["name"] for actor in actors if actor["type"] == "npc"} == {
            npc_id for npc_id in NPC_SCENES if npc_is_present(npc_id, scene.scene_id)
        }, scene.scene_id
        spawn = next(actor for actor in actors if actor["name"] == "player_spawn")
        targets = [actor for actor in actors if actor["type"] in ("npc", "landmark")]
        assert targets, scene.scene_id
        walkable = lambda x, y: any(_contains(polygon, x, y) for polygon in polygons)
        assert walkable(spawn["x"], spawn["y"]), scene.scene_id
        pending = deque([(spawn["x"], spawn["y"])])
        visited = set(pending)
        reached = set()
        while pending:
            x, y = pending.popleft()
            for target in targets:
                if (target["x"] - x) ** 2 + (target["y"] - y) ** 2 < 110 ** 2:
                    reached.add(target["name"])
            for dx, dy in ((16, 0), (-16, 0), (0, 16), (0, -16)):
                point = x + dx, y + dy
                if point not in visited and walkable(*point):
                    visited.add(point)
                    pending.append(point)
        assert reached == {target["name"] for target in targets}, scene.scene_id


def test_legacy_cached_scene_views_restore_the_correct_map():
    for scene_id, scene in SCENES.items():
        old = project_player_view(GameState(session_id="old", current_scene_id=scene_id)).current_scene.model_dump()
        old.pop("tilemap_url")
        assert PlayerSceneView.model_validate(old).tilemap_url == scene.tilemap_url
