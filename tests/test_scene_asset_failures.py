"""A failed GPU request must leave a playable world and bounded retry history."""

import time
from uuid import uuid4
from fastapi.testclient import TestClient
from backend.main import create_app


def test_gpu_timeout_is_retried_twice_then_preserves_world(tmp_path):
    class FailingGateway:
        calls = 0

        async def generate(self, kind, seed):
            self.calls += 1
            raise TimeoutError("simulated GPU timeout")

    gateway = FailingGateway()
    with TestClient(
        create_app(
            f"sqlite+aiosqlite:///{tmp_path / 'timeout.db'}", asset_gateway=gateway
        )
    ) as client:
        client.post("/api/game/start", json={"session_id": "timeout"})
        turn = client.post(
            "/api/game/turn",
            json={
                "session_id": "timeout",
                "action_id": str(uuid4()),
                "expected_state_version": 1,
                "action_mode": "scene_command",
                "message": "生成 0 棵樹、0 個符石、1 座祭壇",
            },
        ).json()
        jobs = client.post(
            "/api/game/timeout/scene-assets", json={"expected_state_version": 2}
        ).json()
        assert len(jobs) == 1
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            final = client.get(
                f"/api/game/timeout/scene-assets/{jobs[0]['job_id']}"
            ).json()
            if final["status"] == "fallback":
                break
            time.sleep(0.02)
        assert final["status"] == "fallback"
        assert final["attempt_count"] == gateway.calls == 2
        assert final["model_url"] == "/game/models/altar-v1.glb"
        assert final["error_code"] == "TimeoutError"
        assert client.get("/api/game/timeout/state").json() == turn["state"]
