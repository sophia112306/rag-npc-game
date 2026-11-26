"""NPC 依信任度調整語氣：後端把關係值換算成低／中／高，NPC 模型看不到數值本身。"""

import json
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import httpx
import pytest

from backend.content.characters import CHARACTER_PROFILES
from backend.generation.gateway import ModelTurnRequest
from backend.generation.openai_compatible_gateway import OpenAICompatibleChatGateway
from backend.generation.planner import GatewayStoryPlanner
from backend.rules.state_rules import MENMESVENTO_MODES, VIDALIA_MODES, npc_behavior_mode, npc_trust_tier
from backend.schemas.content import NPCGenerationContext
from backend.schemas.game_state import GameState, PlayerState, StoryPhase
from backend.schemas.parsed_action import ParsedAction
from backend.schemas.player_action import PlayerAction


@pytest.mark.parametrize(
    ("npc_id", "relation", "expected"),
    [
        ("vidalia", 39, "低"),
        ("vidalia", 40, "中"),
        ("vidalia", 59, "中"),
        ("vidalia", 60, "高"),
        ("andre", 20, "低"),
        ("andre", 40, "中"),
        ("andre", 60, "高"),
        ("menmesvento", 10, "低"),
        ("menmesvento", 11, "中"),
        ("menmesvento", 30, "中"),
        ("menmesvento", 60, "高"),
        ("menmesvento", 79, "高"),
        ("menmesvento", 80, "至高"),
        ("menmesvento", 100, "至高"),
        ("seth", 90, None),
        ("veta", 30, None),
    ],
)
def test_relation_maps_to_training_trust_tiers(npc_id, relation, expected) -> None:
    assert npc_trust_tier(npc_id, relation) == expected


@pytest.mark.parametrize(
    ("relation", "axis", "phase", "mode"),
    [
        (65, -25, StoryPhase.ACT3_FREEDOM, "attached"),
        (65, 25, StoryPhase.ACT3_FREEDOM, "wavering"),
        (65, 0, StoryPhase.ACT3_FREEDOM, "observer"),
        (45, -40, StoryPhase.ACT3_FREEDOM, "observer"),
        (65, -25, StoryPhase.ACT4_ENDING, "ending"),
    ],
)
def test_vidalia_mode_follows_relation_times_axis(relation, axis, phase, mode) -> None:
    assert npc_behavior_mode("vidalia", relation, axis, phase) == VIDALIA_MODES[mode]


def test_menmesvento_mode_follows_trust_tier_and_other_npcs_have_none() -> None:
    assert npc_behavior_mode("menmesvento", 5, 0, StoryPhase.ACT2_MIDTERM) == MENMESVENTO_MODES["低"]
    assert npc_behavior_mode("menmesvento", 85, 0, StoryPhase.ACT3_FREEDOM) == MENMESVENTO_MODES["至高"]
    assert npc_behavior_mode("andre", 70, 0, StoryPhase.ACT3_FREEDOM) is None
    assert npc_behavior_mode("seth", 70, 0, StoryPhase.ACT3_FREEDOM) is None


def test_modes_fit_the_request_field_and_hide_numbers() -> None:
    for text in (*MENMESVENTO_MODES.values(), *VIDALIA_MODES.values()):
        assert len(text) <= 200
        assert not any(char.isdigit() for char in text)


class ContextProvider:
    async def get_generation_context(self, session_id, npc_id, current_turn):
        return NPCGenerationContext(
            npc_id=npc_id,
            setting_version=1,
            public_profile=CHARACTER_PROFILES["vidalia"].model_dump(mode="json"),
            private_profile={},
            knowledge=[],
            memories=[],
            missing_data=[],
        )


class RecordingGateway:
    def __init__(self) -> None:
        self.requests: list[ModelTurnRequest] = []

    async def generate_story(self, request: ModelTurnRequest) -> Mapping[str, Any]:
        self.requests.append(request)
        return {
            "intent_summary": "Reply.",
            "npc_dialogue": [{"text": "……說吧。", "emotion": None}],
            "event_proposals": [],
        }


async def _request_for(npc_id: str, relation: int, axis: int = 0) -> ModelTurnRequest:
    gateway = RecordingGateway()
    planner = GatewayStoryPlanner(gateway, ContextProvider())
    state = GameState(
        session_id="trust",
        current_scene_id="minglin",
        player=PlayerState(player_id="player"),
        story_phase=StoryPhase.ACT3_FREEDOM,
        axis=axis,
    )
    state.npc_states[npc_id].relation = relation
    action = PlayerAction(
        session_id="trust",
        action_id=uuid4(),
        message="妳還記得我嗎？",
        target_npc_id=npc_id,
        expected_state_version=1,
    )
    await planner.propose(action, ParsedAction(intent="dialogue", target_ids=[npc_id]), state)
    return gateway.requests[0]


@pytest.mark.asyncio
async def test_planner_sends_trust_tier_without_raw_relation() -> None:
    request = await _request_for("vidalia", 65, axis=-30)

    assert request.npc_trust == "高"
    assert request.npc_mode == VIDALIA_MODES["attached"]
    serialized = request.model_dump_json()
    assert '"relation"' not in serialized
    assert '"axis"' not in serialized


@pytest.mark.asyncio
async def test_untracked_npc_gets_no_trust_tier() -> None:
    request = await _request_for("seth", 30)

    assert request.npc_trust is None
    assert request.npc_mode is None


@pytest.mark.asyncio
async def test_npc_prompt_explains_and_carries_trust_tier() -> None:
    captured: dict[str, Any] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"finish_reason": "stop", "message": {
            "content": json.dumps({"intent_summary": "Reply.", "npc_dialogue": [{"text": "嗯。", "emotion": None}],
                                   "event_proposals": []}, ensure_ascii=False)
        }}]})

    request = await _request_for("menmesvento", 5)
    gateway = OpenAICompatibleChatGateway(
        "https://model.example/v1", "menmesvento-lora", transport=httpx.MockTransport(handler)
    )
    await gateway.generate_story(request)

    messages = captured["payload"]["messages"]
    assert "npc_trust" in messages[0]["content"]
    assert "never mention trust levels" in messages[0]["content"]
    assert '"信任度": "低"' in messages[1]["content"]
    assert MENMESVENTO_MODES["低"] in messages[1]["content"]
