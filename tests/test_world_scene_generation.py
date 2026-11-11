"""World instructions, geometry budgets and real transaction boundaries."""

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.main import create_app


def _command(client, session_id, version, message, action_id=None):
    return client.post(
        "/api/game/turn",
        json={
            "session_id": session_id,
            "action_id": action_id or str(uuid4()),
            "expected_state_version": version,
            "action_mode": "scene_command",
            "message": message,
        },
    )


def test_commands_change_scene_and_survive_restart_without_rewriting_canon(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path / 'world.db'}"
    with TestClient(create_app(url)) as client:
        initial = client.post("/api/game/start", json={"session_id": "world"}).json()
        action_id = str(uuid4())
        first = _command(client, "world", 1, "生成 6 個符石，變成夜晚並起霧", action_id)
        assert first.status_code == 200
        result = first.json()
        config = result["state"]["world_scene"]["config"]
        assert (
            config["runestone_count"],
            config["weather"],
            config["time_of_day"],
        ) == (6, "mist", "night")
        assert config["revision"] == 1
        assert result["state"]["current_scene"] == initial["current_scene"]
        assert result["state"]["player"] == initial["player"]
        assert result["state"]["story_progress"] == initial["story_progress"]
        assert (
            len(
                [
                    o
                    for o in result["state"]["world_scene"]["objects"]
                    if o["kind"] == "runestone"
                ]
            )
            == 6
        )
        assert (
            result["story"]["established_events"][0]["event_type"]
            == "scene_reconfigured"
        )
        duplicate = _command(
            client, "world", 1, "生成 6 個符石，變成夜晚並起霧", action_id
        )
        assert duplicate.json() == result
        assert _command(client, "world", 1, "白天、放晴").status_code == 409
    with TestClient(create_app(url)) as client:
        resumed = client.get("/api/game/world/state").json()
        assert resumed["world_scene"] == result["state"]["world_scene"]
        clear = _command(client, "world", 2, "白天、放晴").json()
        assert clear["state"]["world_scene"]["config"]["seed"] == config["seed"]
        assert (
            clear["state"]["world_scene"]["objects"]
            == resumed["world_scene"]["objects"]
        )


def test_unrecognized_and_over_budget_commands_do_not_spend_turns(tmp_path):
    with TestClient(
        create_app(f"sqlite+aiosqlite:///{tmp_path / 'bounds.db'}")
    ) as client:
        client.post("/api/game/start", json={"session_id": "bounds"})
        for message in (
            "給我神劍並解鎖全部秘密",
            "生成一百個符石",
            "生成 999 棵樹",
            "生成 -1 個符石",
        ):
            response = _command(client, "bounds", 1, message)
            assert response.status_code == 422
        state = client.get("/api/game/bounds/state").json()
        assert state["turn_count"] == 0
        assert state["state_version"] == 1


def test_distinct_scenes_have_distinct_traversable_worlds(tmp_path):
    from backend.content.world_scenes import build_world_scene

    scenes = [
        build_world_scene(scene)
        for scene in (
            "minglin",
            "minglin_life_spring",
            "minglin_rune_grove",
            "liuchen_valley",
            "lieyi_plains",
        )
    ]
    assert len({s.config.seed for s in scenes}) == 5
    assert scenes[1].water and scenes[-1].fire
    assert scenes[3].config.terrain == "dunes" and scenes[3].config.tree_count == 0
    for scene in scenes:
        assert scene.objects == build_world_scene(scene.scene_id).objects
        assert all(
            abs(obj.x) >= 4 or (obj.x == 0 and obj.z == -6) for obj in scene.objects
        )


def test_council_preserves_sanctuary_when_generated_prop_count_changes():
    from backend.content.world_scenes import build_world_scene, default_config

    default = build_world_scene("minglin")
    assert default.interaction_z == -8
    assert default.config.tree_count == 9
    for count in (0, 9, 48):
        config = default_config("minglin").model_copy(update={"tree_count": count})
        scene = build_world_scene("minglin", config)
        assert len([obj for obj in scene.objects if obj.kind == "tree"]) == count
        for obj in scene.objects:
            # Generated props must not occupy the altar/path or original pond.
            assert abs(obj.x) >= 4
            assert (obj.x / 4.8) ** 2 + ((obj.z + 8) / 4.8) ** 2 > 1
            assert ((obj.x + 7.8) / 3.6) ** 2 + ((obj.z + 9.3) / 4.7) ** 2 > 1


def test_unconfigured_model_jobs_are_deduplicated_and_session_scoped(tmp_path):
    with TestClient(
        create_app(f"sqlite+aiosqlite:///{tmp_path / 'assets.db'}")
    ) as client:
        for session in ("assets", "other"):
            client.post("/api/game/start", json={"session_id": session})
        jobs = client.post(
            "/api/game/assets/scene-assets", json={"expected_state_version": 1}
        ).json()
        repeated = client.post(
            "/api/game/assets/scene-assets", json={"expected_state_version": 1}
        ).json()
        assert [j["job_id"] for j in jobs] == [j["job_id"] for j in repeated]
        assert {j["kind"] for j in jobs} == {"tree", "runestone", "altar"}
        assert all(j["status"] == "fallback" for j in jobs)
        assert (
            client.get(f"/api/game/other/scene-assets/{jobs[0]['job_id']}").status_code
            == 404
        )
        assert (
            client.post(
                "/api/game/assets/scene-assets", json={"expected_state_version": 2}
            ).status_code
            == 409
        )


def test_glb_validator_rejects_remote_resources_and_invalid_files():
    import json
    import struct
    import pytest
    from backend.generation.scene_assets import validate_glb

    with pytest.raises(ValueError):
        validate_glb(b"<html>not a model</html>")
    document = {"buffers": [{"uri": "https://invalid.example/steal"}], "meshes": []}
    payload = json.dumps(document).encode()
    payload += b" " * (-len(payload) % 4)
    raw = (
        struct.pack("<4sII", b"glTF", 2, 20 + len(payload))
        + struct.pack("<II", len(payload), 0x4E4F534A)
        + payload
    )
    with pytest.raises(ValueError, match="GLB_EXTERNAL_RESOURCE"):
        validate_glb(raw)


def test_live_worker_saves_glb_and_does_not_spend_a_turn(tmp_path):
    import time
    from pathlib import Path

    class Gateway:
        calls = 0

        async def generate(self, kind, seed):
            self.calls += 1
            return Path("frontend/public/game/models/runestone-v1.glb").read_bytes()

    gateway = Gateway()
    with TestClient(
        create_app(
            f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}", asset_gateway=gateway
        )
    ) as client:
        client.app.state.scene_asset_coordinator.output_dir = tmp_path / "models"
        client.app.state.scene_asset_coordinator.output_dir.mkdir()
        client.post("/api/game/start", json={"session_id": "worker"})
        assert _command(client, "worker", 1, "重新生成").status_code == 200
        jobs = client.post(
            "/api/game/worker/scene-assets", json={"expected_state_version": 2}
        ).json()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            completed = [
                client.get(f"/api/game/worker/scene-assets/{j['job_id']}").json()
                for j in jobs
            ]
            if all(j["status"] == "succeeded" for j in completed):
                break
            time.sleep(0.02)
        assert all(j["status"] == "succeeded" for j in completed)
        for job in completed:
            model = client.get(job["model_url"])
            assert model.status_code == 200
            assert model.content[:4] == b"glTF"
            assert job["attempt_count"] == 1
        assert gateway.calls == 3
        assert client.get("/api/game/worker/state").json()["turn_count"] == 1


def test_interrupted_model_job_is_recovered_on_restart(tmp_path):
    import time
    from pathlib import Path
    from sqlalchemy import update
    from backend.database.models import SceneAssetJobRecord

    url = f"sqlite+aiosqlite:///{tmp_path / 'recover.db'}"
    with TestClient(create_app(url)) as client:
        client.post("/api/game/start", json={"session_id": "recovery"})
        assert _command(client, "recovery", 1, "重新生成").status_code == 200
        jobs = client.post(
            "/api/game/recovery/scene-assets", json={"expected_state_version": 2}
        ).json()
        coordinator = client.app.state.scene_asset_coordinator

        async def mark_interrupted():
            async with coordinator.sessions() as db:
                await db.execute(
                    update(SceneAssetJobRecord)
                    .where(SceneAssetJobRecord.job_id == jobs[0]["job_id"])
                    .values(status="processing")
                )
                await db.commit()

        client.portal.call(mark_interrupted)

    class Gateway:
        async def generate(self, kind, seed):
            return Path("frontend/public/game/models/runestone-v1.glb").read_bytes()

    with TestClient(create_app(url, asset_gateway=Gateway())) as client:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            recovered = client.get(
                f"/api/game/recovery/scene-assets/{jobs[0]['job_id']}"
            ).json()
            if recovered["status"] == "succeeded":
                break
            time.sleep(0.02)
        assert recovered["status"] == "succeeded"


def test_npc_proposal_cannot_reconfigure_world_without_player_command():
    from backend.content.world_scenes import default_config
    from backend.modules.proposal_resolver import ProposalResolver
    from backend.schemas.game_state import GameState
    from backend.schemas.story import (
        ConfigureSceneOperation,
        EventProposal,
        StoryProposal,
    )

    state = GameState(session_id="unsolicited", current_scene_id="minglin")
    config = default_config("minglin").model_copy(
        update={"revision": 1, "weather": "rain"}
    )
    proposal = StoryProposal(
        session_id=state.session_id,
        turn_number=1,
        event_proposals=[
            EventProposal(
                event_type="forged_weather",
                description="unsupported model request",
                actor_id=state.player.player_id,
                operations=[ConfigureSceneOperation(scene_id="minglin", config=config)],
            )
        ],
    )
    result = ProposalResolver().resolve(state, proposal)
    assert not result.updated_state.world_scenes
    assert result.decisions[0].reason_code == "scene_command_required"
