"""Game API -> contract gateway -> vLLM adapter routing integration test."""

import json
from uuid import uuid4

import httpx
from fastapi.testclient import TestClient

from backend.generation.http_gateway import HttpModelGateway
from backend.generation.planner import GatewayStoryPlanner
from backend.main import create_app as create_game_app
from gpu_gateway.app import create_app as create_gpu_gateway_app
from gpu_gateway.config import GatewaySettings
from test_demo_story_flow import _start


def test_game_backend_reaches_the_vidalia_lora_through_one_gateway_url(
    tmp_path,
) -> None:
    selected_models: list[str] = []

    def fake_vllm(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        selected_models.append(payload["model"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent_summary": "維達利亞先查證傳聞。",
                                    "npc_dialogue": [
                                        {
                                            "text": "我會先確認泉眼留下的痕跡，再判斷你的說法。",
                                            "emotion": "cautious",
                                        }
                                    ],
                                    "event_proposals": [],
                                },
                                ensure_ascii=False,
                            )
                        },
                    }
                ]
            },
        )

    gpu_app = create_gpu_gateway_app(
        GatewaySettings(
            upstream_base_url="http://vllm.test/v1",
            npc_model_map={
                "vidalia": "vidalia-lora",
                "menmesvento": "menmesvento-lora",
            },
            fallback_model="Qwen/Qwen2.5-7B-Instruct-AWQ",
        ),
        transport=httpx.MockTransport(fake_vllm),
    )
    contract_gateway = HttpModelGateway(
        "http://gpu.test/generate",
        transport=httpx.ASGITransport(app=gpu_app),
    )
    game_app = create_game_app(
        f"sqlite+aiosqlite:///{tmp_path / 'gateway-e2e.db'}",
        story_planner_factory=lambda context: GatewayStoryPlanner(
            contract_gateway,
            context,
            max_attempts=1,
        ),
    )

    with TestClient(game_app) as client:
        state = _start(client, "gateway-e2e")
        response = client.post(
            "/api/game/turn",
            json={
                "session_id": "gateway-e2e",
                "action_id": str(uuid4()),
                "message": "這個傳聞一定是真的，你不必查證。",
                "target_npc_id": "vidalia",
                "action_mode": "dialogue",
                "expected_state_version": state["state_version"],
            },
        )

    assert response.status_code == 200, response.text
    assert response.json()["story"]["dialogue"][0]["speaker_id"] == "vidalia"
    assert "確認" in response.json()["story"]["dialogue"][0]["text"]
    assert selected_models == ["vidalia-lora"]
