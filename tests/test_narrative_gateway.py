"""GPU gateway /narrate：基礎模型判讀玩家發言，輸出經過夾值的 NarrativeAIResponse。"""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.generation.gateway import ModelGatewayTransientError
from backend.schemas.narrative_ai import NarrativeAIRequest
from gpu_gateway.app import create_app
from gpu_gateway.config import DEFAULT_BASE_MODEL, GatewaySettings
from backend.schemas.narrative_ai import AXIS_STANCES
from gpu_gateway.narrator import (
    NARRATOR_SYSTEM_PROMPT,
    NARRATOR_VERIFICATION_PROMPT,
    NarrativeAdapter,
    parse_narrator_output,
)


REQUEST = NarrativeAIRequest(
    player_message="我想留在鳴霖陪妳",
    target_npc_id="vidalia",
    target_npc_name="維達利亞",
    scene_id="minglin",
    scene_name="鳴霖",
    story_phase="Act2_Midterm",
    axis=-10,
    usurp=5,
    truth_level=1,
    relations={"andre": 20, "vidalia": 45, "menmesvento": 30},
)


def completion(content: str, finish_reason: str = "stop") -> httpx.Response:
    return httpx.Response(200, json={
        "choices": [{"finish_reason": finish_reason, "message": {"content": content}}]
    })


def test_adapter_uses_base_model_and_clamps_proposal() -> None:
    payloads = []

    def upstream(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return completion(json.dumps({
            "axis": -9, "usurp": -1,
            "stance": "承諾陪伴",
            "relation": {"vidalia": 30, "seth": 5, "andre": 0},
            "reason": "承諾陪伴",
        }, ensure_ascii=False))

    adapter = NarrativeAdapter(GatewaySettings(), transport=httpx.MockTransport(upstream))
    result = asyncio.run(adapter.judge(REQUEST))

    seen = payloads[0]
    assert seen["model"] == DEFAULT_BASE_MODEL
    assert seen["response_format"] == {"type": "json_object"}
    assert "敘事 AI" in seen["messages"][0]["content"]
    assert "我想留在鳴霖陪妳" in seen["messages"][1]["content"]
    assert payloads[1]["messages"][0]["content"] == NARRATOR_VERIFICATION_PROMPT
    assert result.delta.axis == -5
    assert result.axis_reviewed is True
    assert result.delta.usurp == 0
    assert result.delta.relation == {"vidalia": 10}
    assert result.speaker == "vidalia"
    assert result.event_done is None
    assert result.reason == "承諾陪伴"


def test_parser_accepts_fenced_and_nested_delta() -> None:
    text = '```json\n{"delta": {"axis": 3, "usurp": 2, "relation": {"menmesvento": "4"}}, "stance": "主張打破循環", "reason": "談死亡"}\n```'

    result = parse_narrator_output(text, REQUEST)

    assert result.delta.axis == 3
    assert result.delta.usurp == 2
    assert result.delta.relation == {"menmesvento": 4}


@pytest.mark.parametrize(
    ("axis", "stance", "expected"),
    [
        (-3, "承諾陪伴", "承諾陪伴"),
        (4, "主張打破循環", "主張打破循環"),
        (-3, "主張打破循環", None),  # 方向與主軸不符
        (-3, "喜歡下雨", None),  # 不在清單內
        (0, "尋求安寧", None),  # 主軸為 0 不需要類別
    ],
)
def test_parser_keeps_only_valid_stances(axis, stance, expected) -> None:
    text = json.dumps({"reason": "測試", "axis": axis, "stance": stance, "usurp": 0, "relation": {}}, ensure_ascii=False)

    assert parse_narrator_output(text, REQUEST).stance == expected


def test_parser_zeros_axis_without_a_valid_stance() -> None:
    text = json.dumps({
        "reason": "只是一起調查",
        "axis": 4,
        "stance": None,
        "usurp": 0,
        "relation": {"andre": 5},
    }, ensure_ascii=False)

    result = parse_narrator_output(text, REQUEST)

    assert result.delta.axis == 0
    assert result.stance is None
    assert result.delta.relation == {"andre": 5}


def test_prompt_lists_every_stance() -> None:
    for stance in AXIS_STANCES:
        assert stance in NARRATOR_SYSTEM_PROMPT


@pytest.mark.parametrize("content", ["我覺得應該加五分", '["axis", 3]', '{"axis": "很多"}'])
def test_adapter_rejects_unusable_output(content: str) -> None:
    adapter = NarrativeAdapter(
        GatewaySettings(), transport=httpx.MockTransport(lambda request: completion(content))
    )
    with pytest.raises(ModelGatewayTransientError):
        asyncio.run(adapter.judge(REQUEST))


def test_adapter_rejects_truncated_output() -> None:
    adapter = NarrativeAdapter(
        GatewaySettings(),
        transport=httpx.MockTransport(lambda request: completion('{"axis": 1', "length")),
    )
    with pytest.raises(ModelGatewayTransientError):
        asyncio.run(adapter.judge(REQUEST))


def test_adapter_rejudges_reason_delta_contradiction() -> None:
    payloads = []

    def upstream(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            return completion(json.dumps({
                "reason": "閒聊，與立場和角色喜好無關",
                "axis": 0,
                "usurp": 0,
                "relation": {"vidalia": 5},
            }, ensure_ascii=False))
        return completion(json.dumps({
            "reason": "閒聊，與立場和角色喜好無關",
            "axis": 0,
            "usurp": 0,
            "relation": {},
        }, ensure_ascii=False))

    adapter = NarrativeAdapter(
        GatewaySettings(upstream_max_attempts=2),
        transport=httpx.MockTransport(upstream),
    )

    result = asyncio.run(adapter.judge(REQUEST))

    assert len(payloads) == 2
    assert len(payloads[1]["messages"]) == 2
    assert payloads[1]["messages"][0]["content"] == NARRATOR_VERIFICATION_PROMPT
    assert result.delta.relation == {}


def test_adapter_fail_closes_persistent_reason_delta_contradiction() -> None:
    calls = 0

    def upstream(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return completion(json.dumps({
            "reason": "無變化",
            "axis": 4,
            "stance": "主張打破循環",
            "usurp": 2,
            "relation": {"vidalia": 8},
        }, ensure_ascii=False))

    adapter = NarrativeAdapter(
        GatewaySettings(upstream_max_attempts=2),
        transport=httpx.MockTransport(upstream),
    )

    result = asyncio.run(adapter.judge(REQUEST))

    assert calls == 2
    assert result.delta.axis == 0
    assert result.delta.usurp == 0
    assert result.delta.relation == {}
    assert result.stance is None


def test_adapter_rejudges_nonzero_axis_without_valid_stance() -> None:
    payloads = []

    def upstream(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            return completion(json.dumps({
                "reason": "想要長生，偏守夢",
                "axis": -3,
                "stance": None,
                "usurp": 0,
                "relation": {"menmesvento": -5},
            }, ensure_ascii=False))
        return completion(json.dumps({
            "reason": "想要長生，偏守夢",
            "axis": -3,
            "stance": "肯定永生或輪迴",
            "usurp": 0,
            "relation": {"menmesvento": -5},
        }, ensure_ascii=False))

    adapter = NarrativeAdapter(
        GatewaySettings(upstream_max_attempts=2),
        transport=httpx.MockTransport(upstream),
    )

    result = asyncio.run(adapter.judge(REQUEST))

    assert len(payloads) == 2
    assert payloads[1]["messages"][0]["content"] == NARRATOR_VERIFICATION_PROMPT
    assert result.delta.axis == -3
    assert result.stance == "肯定永生或輪迴"
    assert result.axis_reviewed is True


def test_one_pass_axis_is_not_marked_reviewed() -> None:
    adapter = NarrativeAdapter(
        GatewaySettings(upstream_max_attempts=1),
        transport=httpx.MockTransport(lambda _: completion(json.dumps({
            "reason": "想留下，偏守夢", "axis": -3, "stance": "留戀",
            "usurp": 0, "relation": {},
        }, ensure_ascii=False))),
    )

    result = asyncio.run(adapter.judge(REQUEST))

    assert result.delta.axis == -3
    assert result.axis_reviewed is False


def test_event_candidate_requires_second_review_and_legal_label() -> None:
    request = REQUEST.model_copy(update={"legal_event_labels": ["答應他喚醒維塔的請求"]})
    calls = 0

    def upstream(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return completion(json.dumps({
            "reason": "主角明確答應喚醒維塔", "axis": 0, "stance": None,
            "usurp": 0, "relation": {}, "event_done": "答應他喚醒維塔的請求",
        }, ensure_ascii=False))

    result = asyncio.run(NarrativeAdapter(
        GatewaySettings(upstream_max_attempts=2), transport=httpx.MockTransport(upstream)
    ).judge(request))

    assert calls == 2
    assert result.event_done == "答應他喚醒維塔的請求"
    assert result.event_reviewed is True


def test_event_candidate_rejected_on_second_review_stays_unapproved() -> None:
    label = "收下塵歸令"
    request = REQUEST.model_copy(update={"legal_event_labels": [label]})
    calls = 0

    def upstream(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return completion(json.dumps({
            "reason": "玩家明確收下" if calls == 1 else "玩家只是詢問",
            "axis": 0, "stance": None, "usurp": 0, "relation": {},
            "event_done": label if calls == 1 else None,
        }, ensure_ascii=False))

    result = asyncio.run(NarrativeAdapter(
        GatewaySettings(upstream_max_attempts=2), transport=httpx.MockTransport(upstream)
    ).judge(request))

    assert calls == 2
    assert result.event_done is None
    assert result.event_reviewed is False


def test_event_first_proposed_only_on_second_pass_stays_unapproved() -> None:
    label = "收下塵歸令"
    request = REQUEST.model_copy(update={"legal_event_labels": [label]})
    calls = 0

    def upstream(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return completion(json.dumps({
            "reason": "無關" if calls == 1 else "主角明確收下",
            "axis": 0, "stance": None, "usurp": 0, "relation": {},
            "event_done": None if calls == 1 else label,
        }, ensure_ascii=False))

    result = asyncio.run(NarrativeAdapter(
        GatewaySettings(upstream_max_attempts=2), transport=httpx.MockTransport(upstream)
    ).judge(request))

    assert calls == 2
    assert result.event_done == label
    assert result.event_reviewed is False


def test_adapter_verifies_a_zero_effect_decision_once() -> None:
    payloads = []

    def upstream(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return completion(json.dumps({
            "reason": "閒聊，與角色喜好無關",
            "axis": 0,
            "stance": None,
            "usurp": 0,
            "relation": {},
        }, ensure_ascii=False))

    adapter = NarrativeAdapter(
        GatewaySettings(upstream_max_attempts=3),
        transport=httpx.MockTransport(upstream),
    )

    result = asyncio.run(adapter.judge(REQUEST))

    assert len(payloads) == 2
    assert payloads[1]["messages"][0]["content"] == NARRATOR_VERIFICATION_PROMPT
    assert result.delta.relation == {}


def test_adapter_rejudges_relation_that_conflicts_with_its_own_reason() -> None:
    request = REQUEST.model_copy(update={
        "target_npc_id": "menmesvento",
        "target_npc_name": "門梅司文托",
        "player_message": "死亡讓生命有重量，沒有終點的輪迴只是逃避。",
    })
    calls = 0

    def upstream(http_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        relation = -8 if calls < 3 else 6
        return completion(json.dumps({
            "reason": "強調死亡的重要性，否定了無限輪迴",
            "axis": 0,
            "stance": None,
            "usurp": 0,
            "relation": {"menmesvento": relation},
        }, ensure_ascii=False))

    adapter = NarrativeAdapter(
        GatewaySettings(upstream_max_attempts=3),
        transport=httpx.MockTransport(upstream),
    )

    result = asyncio.run(adapter.judge(request))

    assert calls == 3
    assert result.delta.relation == {"menmesvento": 6}


def test_adapter_corrects_persistent_relation_reason_conflict() -> None:
    request = REQUEST.model_copy(update={
        "target_npc_id": "menmesvento",
        "target_npc_name": "門梅司文托",
    })
    adapter = NarrativeAdapter(
        GatewaySettings(upstream_max_attempts=2),
        transport=httpx.MockTransport(lambda _: completion(json.dumps({
            "reason": "支持長生不老",
            "axis": 0,
            "stance": None,
            "usurp": 0,
            "relation": {"menmesvento": 7},
        }, ensure_ascii=False))),
    )

    result = asyncio.run(adapter.judge(request))

    assert result.delta.relation == {"menmesvento": -7}


def test_narrate_endpoint_returns_judgement() -> None:
    app = create_app(
        GatewaySettings(),
        transport=httpx.MockTransport(lambda request: completion('{"axis": 2, "stance": "主張打破循環", "usurp": 0, "relation": {}, "reason": "支持打破循環"}')),
    )
    with TestClient(app) as client:
        response = client.post("/narrate", json=REQUEST.model_dump(mode="json"))

    assert response.status_code == 200, response.text
    assert response.json()["delta"]["axis"] == 2


def test_narrate_endpoint_reports_upstream_failure() -> None:
    app = create_app(
        GatewaySettings(), transport=httpx.MockTransport(lambda request: httpx.Response(500))
    )
    with TestClient(app) as client:
        response = client.post("/narrate", json=REQUEST.model_dump(mode="json"))

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "NARRATOR_MODEL_UNAVAILABLE"


def test_narrate_endpoint_requires_gateway_token_when_configured() -> None:
    app = create_app(
        GatewaySettings(inbound_api_key="secret"),
        transport=httpx.MockTransport(lambda request: completion('{"axis": 0}')),
    )
    with TestClient(app) as client:
        response = client.post("/narrate", json=REQUEST.model_dump(mode="json"))

    assert response.status_code == 401
