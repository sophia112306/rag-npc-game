"""Alan LoRA stays a read-only HUD channel, with an early reveal boundary."""

import httpx
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.schemas.alan_chat import AlanModelResponse
from gpu_gateway.alan import AlanAdapter
from gpu_gateway.config import GatewaySettings


class StubAlanGateway:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        return AlanModelResponse(reply=self.reply)


def test_alan_hud_chat_uses_public_context_without_advancing_turn(tmp_path):
    app = create_app(f"sqlite+aiosqlite:///{tmp_path / 'alan.db'}")
    with TestClient(app) as client:
        state = client.post("/api/game/start", json={"session_id": "alan-test"}).json()
        gateway = StubAlanGateway("請先和安德烈交談，確認林地異象。")
        app.state.alan_gateway = gateway
        result = client.post("/api/game/alan-test/alan/message", json={
            "question": "接下來怎麼辦？", "expected_state_version": state["state_version"]
        })
        assert result.status_code == 200, result.text
        assert "安德烈" in result.json()["reply"]
        sent = gateway.requests[0]
        assert sent.identity_revealed is False
        assert "安德烈" in sent.objective
        assert "評議會" not in sent.model_dump_json()
        after = client.get("/api/game/alan-test/state").json()
        assert after["turn_count"] == state["turn_count"]
        assert after["state_version"] == state["state_version"]


def test_alan_chat_rejects_early_identity_leak(tmp_path):
    app = create_app(f"sqlite+aiosqlite:///{tmp_path / 'alan.db'}")
    with TestClient(app) as client:
        state = client.post("/api/game/start", json={"session_id": "alan-test"}).json()
        app.state.alan_gateway = StubAlanGateway("我是艾倫，來自外部世界。")
        result = client.post("/api/game/alan-test/alan/message", json={
            "question": "你是誰？", "expected_state_version": state["state_version"]
        })
        assert result.status_code == 502
        assert result.json()["detail"]["code"] == "ALAN_RESPONSE_UNSAFE"


def test_gpu_alan_adapter_calls_plain_chat_completion():
    seen = {}

    def upstream(request: httpx.Request) -> httpx.Response:
        seen.update(__import__("json").loads(request.content))
        return httpx.Response(200, json={
            "choices": [{"finish_reason": "stop", "message": {"content": "請向安德烈詢問異象。"}}]
        })

    adapter = AlanAdapter(
        GatewaySettings(npc_model_map={"alan_walker": "alan-walker-lora"}),
        transport=httpx.MockTransport(upstream),
    )
    from backend.schemas.alan_chat import AlanModelRequest
    import asyncio
    result = asyncio.run(adapter.generate(AlanModelRequest(
        question="下一步？", scene_name="鳴霖", objective="與安德烈交談",
        available_actions=["與安德烈交談"], tone="calm",
    )))
    assert result.reply == "請向安德烈詢問異象。"
    assert seen["model"] == "alan-walker-lora"
    assert "response_format" not in seen
