"""Persistent, provider-neutral scene image job API tests."""

from uuid import uuid4

from fastapi.testclient import TestClient

from backend.generation.image_gateway import SceneImageRequest, SceneImageResult
from backend.main import create_app


class FakeImageGateway:
    provider_name = "fake_image_gateway"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[SceneImageRequest] = []

    async def generate(self, request: SceneImageRequest) -> SceneImageResult:
        self.calls.append(request)
        if self.fail:
            raise TimeoutError("simulated image timeout")
        return SceneImageResult(image_url=f"/generated/{request.job_id}.png")


def test_unconfigured_gateway_persists_deduplicated_fallback(tmp_path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'fallback-image.db'}"
    session_id = "fallback-image"

    with TestClient(create_app(database_url)) as client:
        state = client.post("/api/game/start", json={"session_id": session_id}).json()
        first = client.post(
            f"/api/game/{session_id}/scene-image",
            json={"expected_state_version": state["state_version"]},
        )
        duplicate = client.post(
            f"/api/game/{session_id}/scene-image",
            json={"expected_state_version": state["state_version"]},
        )

        assert first.status_code == 202
        assert first.json()["status"] == "fallback"
        assert first.json()["provider"] == "static_fallback"
        assert first.json()["image_url"] == state["current_scene"]["horizon_url"]
        assert first.json()["error_code"] == "IMAGE_GATEWAY_UNCONFIGURED"
        assert duplicate.json()["job_id"] == first.json()["job_id"]

    with TestClient(create_app(database_url)) as restarted:
        resumed = restarted.post(
            f"/api/game/{session_id}/scene-image",
            json={"expected_state_version": state["state_version"]},
        )
        assert resumed.json()["job_id"] == first.json()["job_id"]


def test_configured_gateway_completes_after_response_and_is_cached(tmp_path) -> None:
    gateway = FakeImageGateway()
    session_id = "generated-image"
    with TestClient(
        create_app(
            f"sqlite+aiosqlite:///{tmp_path / 'generated-image.db'}",
            image_gateway=gateway,
        )
    ) as client:
        state = client.post("/api/game/start", json={"session_id": session_id}).json()
        queued = client.post(
            f"/api/game/{session_id}/scene-image",
            json={"expected_state_version": state["state_version"]},
        ).json()
        completed = client.get(
            f"/api/game/{session_id}/scene-image/{queued['job_id']}"
        )
        duplicate = client.post(
            f"/api/game/{session_id}/scene-image",
            json={"expected_state_version": state["state_version"]},
        )

        assert completed.status_code == 200
        assert completed.json()["status"] == "succeeded"
        assert completed.json()["image_url"].startswith("/generated/")
        assert completed.json()["attempt_count"] == 1
        assert duplicate.json()["job_id"] == queued["job_id"]
        assert len(gateway.calls) == 1
        assert "Revealed public clue IDs" in gateway.calls[0].prompt
        assert "玩家說" not in gateway.calls[0].prompt


def test_gateway_failure_falls_back_without_changing_game_state(tmp_path) -> None:
    gateway = FakeImageGateway(fail=True)
    session_id = "failed-image"
    with TestClient(
        create_app(
            f"sqlite+aiosqlite:///{tmp_path / 'failed-image.db'}",
            image_gateway=gateway,
        )
    ) as client:
        state = client.post("/api/game/start", json={"session_id": session_id}).json()
        queued = client.post(
            f"/api/game/{session_id}/scene-image",
            json={"expected_state_version": state["state_version"]},
        ).json()
        completed = client.get(
            f"/api/game/{session_id}/scene-image/{queued['job_id']}"
        ).json()
        unchanged = client.get(f"/api/game/{session_id}/state").json()

        assert completed["status"] == "fallback"
        assert completed["error_code"] == "TimeoutError"
        assert completed["image_url"] == state["current_scene"]["horizon_url"]
        assert unchanged["state_version"] == state["state_version"]
        assert unchanged["turn_count"] == state["turn_count"]


def test_scene_image_api_rejects_stale_version_and_cross_session_lookup(tmp_path) -> None:
    with TestClient(
        create_app(f"sqlite+aiosqlite:///{tmp_path / 'image-boundary.db'}")
    ) as client:
        first = client.post("/api/game/start", json={"session_id": "image-a"}).json()
        client.post("/api/game/start", json={"session_id": "image-b"})
        conflict = client.post(
            "/api/game/image-a/scene-image",
            json={"expected_state_version": first["state_version"] + 1},
        )
        job = client.post(
            "/api/game/image-a/scene-image",
            json={"expected_state_version": first["state_version"]},
        ).json()
        hidden = client.get(f"/api/game/image-b/scene-image/{job['job_id']}")
        missing = client.get(
            f"/api/game/image-a/scene-image/{uuid4()}"
        )

        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "STATE_VERSION_CONFLICT"
        assert hidden.status_code == 404
        assert missing.status_code == 404
