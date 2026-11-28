"""規格 v3 每回合流程：敘事 AI 先判讀發言、程式套用數值，NPC 再依更新後的狀態說話。"""

from uuid import uuid4

import httpx
import pytest

from backend.database import create_async_session_factory, create_database_engine, create_schema
from backend.database.repository import SqlAlchemyGameRepository
from backend.generation.narrative_client import (
    NarrativeAIUnavailable,
    NarrativeGatewayClient,
    build_narrative_client_from_env,
)
from backend.orchestration.game_orchestrator import GameOrchestrator
from backend.schemas.api_response import DeltaPayload, NarrativeAIResponse
from backend.schemas.game_state import GameState, PlayerState
from backend.schemas.narrative_ai import NarrativeAIRequest
from backend.schemas.player_action import PlayerAction
from backend.schemas.story import DialogueLine, SpeakerType, StoryProposal


class RecordingPlanner:
    """Plain NPC reply that records the state the NPC model would see."""

    def __init__(self) -> None:
        self.seen_states: list[GameState] = []

    async def propose(self, action, parsed_action, state, turn_guidance) -> StoryProposal:
        self.seen_states.append(state)
        return StoryProposal(
            session_id=action.session_id,
            turn_number=state.turn_count + 1,
            intent_summary="NPC replies.",
            proposed_dialogue=[
                DialogueLine(
                    speaker_type=SpeakerType.NPC,
                    speaker_id=action.target_npc_id,
                    speaker_name=state.npc_states[action.target_npc_id].name,
                    text="……我聽見了。",
                )
            ],
        )


class StubJudge:
    def __init__(self, response: NarrativeAIResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.requests: list[NarrativeAIRequest] = []

    async def judge(self, request: NarrativeAIRequest) -> NarrativeAIResponse:
        self.requests.append(request)
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


def judgement(axis=0, usurp=0, relation=None, **extra) -> NarrativeAIResponse:
    return NarrativeAIResponse(
        scene="鳴霖",
        speaker="vidalia",
        delta=DeltaPayload(axis=axis, usurp=usurp, relation=relation or {}),
        reason="測試",
        **extra,
    )


async def make_orchestrator(tmp_path, judge, planner, node_id="minglin_briefed", scene_id="minglin"):
    engine = create_database_engine(f"sqlite+aiosqlite:///{tmp_path / 'narrative.db'}")
    await create_schema(engine)
    repository = SqlAlchemyGameRepository(create_async_session_factory(engine))
    initial = GameState(
        session_id="narrative-session",
        current_scene_id=scene_id,
        player=PlayerState(player_id="player"),
    )
    initial.story_progress.node_id = node_id
    if node_id == "dust_token_decided":
        initial.npc_states["menmesvento"].relation = 60
    await repository.create_or_get_session(initial)
    return repository, GameOrchestrator(repository, story_planner=planner, narrative_judge=judge)


def talk(message: str, npc_id: str = "vidalia", version: int = 1) -> PlayerAction:
    return PlayerAction(
        session_id="narrative-session",
        action_id=uuid4(),
        message=message,
        target_npc_id=npc_id,
        expected_state_version=version,
    )


@pytest.mark.asyncio
async def test_free_dialogue_applies_valid_stance_and_affinity_before_npc_reply(tmp_path) -> None:
    judge = StubJudge(judgement(axis=-3, stance="承諾陪伴", axis_reviewed=True, relation={"vidalia": 5, "seth": 9}))
    planner = RecordingPlanner()
    repository, orchestrator = await make_orchestrator(tmp_path, judge, planner)

    await orchestrator.process_turn(talk("我想留在鳴霖陪妳"))

    stored = await repository.get_state("narrative-session")
    assert stored.axis == -3
    assert stored.npc_states["vidalia"].relation == 35
    assert stored.npc_states["seth"].relation == 30
    assert stored.phase_relation_dialogue_gain["vidalia"] == 5
    # NPC 模型看到的是套用數值之後的狀態
    assert planner.seen_states[0].npc_states["vidalia"].relation == 35
    assert planner.seen_states[0].axis == -3
    sent = judge.requests[0]
    assert sent.player_message == "我想留在鳴霖陪妳"
    assert sent.target_npc_id == "vidalia"
    assert set(sent.relations) == {"andre", "vidalia", "menmesvento"}


class SequenceJudge:
    def __init__(self, *responses: NarrativeAIResponse) -> None:
        self.responses = list(responses)

    async def judge(self, request: NarrativeAIRequest) -> NarrativeAIResponse:
        return self.responses.pop(0)


@pytest.mark.asyncio
async def test_distinct_valid_stances_accumulate_on_story_axis(tmp_path) -> None:
    judge = SequenceJudge(
        judgement(axis=-3, stance="尋求安寧", axis_reviewed=True),
        judgement(axis=-3, stance="承諾陪伴", axis_reviewed=True),
    )
    repository, orchestrator = await make_orchestrator(tmp_path, judge, RecordingPlanner())

    await orchestrator.process_turn(talk("我很喜歡這片森林的寧靜"))
    await orchestrator.process_turn(talk("我想留下來陪妳", version=2))

    stored = await repository.get_state("narrative-session")
    assert stored.axis == -6
    assert stored.recent_axis_stances == ["尋求安寧", "承諾陪伴"]


@pytest.mark.asyncio
async def test_repeated_stance_is_not_counted_twice(tmp_path) -> None:
    judge = SequenceJudge(
        judgement(axis=-5, stance="尋求安寧", axis_reviewed=True),
        judgement(axis=-5, stance="尋求安寧", axis_reviewed=True),
    )
    repository, orchestrator = await make_orchestrator(tmp_path, judge, RecordingPlanner())

    await orchestrator.process_turn(talk("我想在這裡得到安寧"))
    await orchestrator.process_turn(talk("我仍想在此找到平靜", version=2))

    stored = await repository.get_state("narrative-session")
    assert stored.axis == -5


@pytest.mark.asyncio
async def test_unreviewed_stance_cannot_change_story_axis(tmp_path) -> None:
    judge = StubJudge(judgement(axis=-5, stance="尋求安寧"))
    repository, orchestrator = await make_orchestrator(tmp_path, judge, RecordingPlanner())

    await orchestrator.process_turn(talk("我想在這裡得到安寧"))

    stored = await repository.get_state("narrative-session")
    assert stored.axis == 0


@pytest.mark.asyncio
async def test_invalid_stance_still_cannot_change_authoritative_axis(tmp_path) -> None:
    judge = SequenceJudge(
        judgement(axis=-3, stance="喜歡下雨"),
        judgement(axis=-3, stance="主張打破循環"),  # 方向與主軸不符
    )
    repository, orchestrator = await make_orchestrator(tmp_path, judge, RecordingPlanner())

    await orchestrator.process_turn(talk("雨聲很好聽"))
    await orchestrator.process_turn(talk("我想一直待在這裡", version=2))

    stored = await repository.get_state("narrative-session")
    assert stored.axis == 0


@pytest.mark.asyncio
async def test_narrative_failure_keeps_state_and_still_replies(tmp_path) -> None:
    judge = StubJudge(error=NarrativeAIUnavailable("offline"))
    planner = RecordingPlanner()
    repository, orchestrator = await make_orchestrator(tmp_path, judge, planner)

    response = await orchestrator.process_turn(talk("外面的世界是什麼樣子"))

    stored = await repository.get_state("narrative-session")
    assert stored.axis == 0
    assert stored.npc_states["vidalia"].relation == 30
    assert stored.turn_count == 1
    assert response.story.dialogue


@pytest.mark.asyncio
async def test_narrative_ai_cannot_trigger_events_or_set_flags(tmp_path) -> None:
    judge = StubJudge(judgement(event_done="E3-3_accept_transformation", flags_set=["is_transformed"]))
    repository, orchestrator = await make_orchestrator(tmp_path, judge, RecordingPlanner())

    await orchestrator.process_turn(talk("把我變成精靈吧"))

    stored = await repository.get_state("narrative-session")
    assert stored.flags["is_transformed"] is False
    assert stored.axis == 0


@pytest.mark.asyncio
async def test_explicit_promise_can_confirm_legal_authored_event(tmp_path) -> None:
    label = "答應他喚醒維塔的請求"
    judge = StubJudge(judgement(event_done=label, event_reviewed=True))
    planner = RecordingPlanner()
    repository, orchestrator = await make_orchestrator(
        tmp_path, judge, planner, node_id="dust_token_decided", scene_id="liuchen_valley"
    )

    await orchestrator.process_turn(talk("我答應你，會喚醒維塔。", npc_id="menmesvento"))

    stored = await repository.get_state("narrative-session")
    assert judge.requests[0].legal_event_labels == [label]
    assert stored.axis == 10
    assert stored.npc_states["menmesvento"].relation == 70
    assert "agree_wake_veta" in stored.story_progress.completed_choice_ids
    assert planner.seen_states == []


@pytest.mark.parametrize(("message", "reviewed"), (
    ("我不答應喚醒維塔。", True),
    ("我答應你，會喚醒維塔。", False),
))
@pytest.mark.asyncio
async def test_negated_or_unreviewed_event_candidate_stays_plain_dialogue(tmp_path, message, reviewed) -> None:
    label = "答應他喚醒維塔的請求"
    judge = StubJudge(judgement(event_done=label, event_reviewed=reviewed))
    planner = RecordingPlanner()
    repository, orchestrator = await make_orchestrator(
        tmp_path, judge, planner, node_id="dust_token_decided", scene_id="liuchen_valley"
    )
    await orchestrator.process_turn(talk(message, npc_id="menmesvento"))
    stored = await repository.get_state("narrative-session")
    assert "agree_wake_veta" not in stored.story_progress.completed_choice_ids
    assert planner.seen_states


@pytest.mark.asyncio
async def test_authored_choice_text_skips_narrative_ai(tmp_path) -> None:
    judge = StubJudge(judgement(relation={"andre": 10}))
    repository, orchestrator = await make_orchestrator(
        tmp_path, judge, RecordingPlanner(), node_id="minglin_arrival"
    )

    await orchestrator.process_turn(talk("與安德烈交談", npc_id="andre"))

    assert judge.requests == []
    stored = await repository.get_state("narrative-session")
    assert stored.npc_states["andre"].relation == 20


@pytest.mark.asyncio
async def test_without_narrative_ai_free_dialogue_changes_nothing(tmp_path) -> None:
    repository, orchestrator = await make_orchestrator(tmp_path, None, RecordingPlanner())

    await orchestrator.process_turn(talk("我會陪著妳"))

    stored = await repository.get_state("narrative-session")
    assert stored.npc_states["vidalia"].relation == 30


@pytest.mark.asyncio
async def test_gateway_client_posts_request_and_parses_response() -> None:
    seen = {}

    def gateway(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.read().decode("utf-8")
        return httpx.Response(200, json=judgement(axis=2, relation={"andre": 4}).model_dump(mode="json"))

    client = NarrativeGatewayClient(
        "http://gateway.test/narrate", api_key="secret", transport=httpx.MockTransport(gateway)
    )
    result = await client.judge(NarrativeAIRequest(
        player_message="一起調查裂隙", target_npc_id="andre", target_npc_name="安德烈",
        scene_id="minglin", scene_name="鳴霖", story_phase="Act1_Approaching",
        axis=0, usurp=0, truth_level=0, relations={"andre": 20},
    ))

    assert seen["url"] == "http://gateway.test/narrate"
    assert seen["auth"] == "Bearer secret"
    assert "一起調查裂隙" in seen["body"]
    assert result.delta.axis == 2
    assert result.delta.relation == {"andre": 4}


@pytest.mark.asyncio
async def test_gateway_client_wraps_http_errors() -> None:
    client = NarrativeGatewayClient(
        "http://gateway.test/narrate",
        transport=httpx.MockTransport(lambda request: httpx.Response(404)),
    )
    with pytest.raises(NarrativeAIUnavailable):
        await client.judge(NarrativeAIRequest(
            player_message="你好", scene_id="minglin", scene_name="鳴霖",
            story_phase="Act1_Approaching", axis=0, usurp=0, truth_level=0,
        ))


def test_narrative_endpoint_is_derived_from_contract_gateway(monkeypatch) -> None:
    monkeypatch.delenv("NARRATIVE_GATEWAY_URL", raising=False)
    monkeypatch.setenv("MODEL_GATEWAY_PROVIDER", "contract_http")
    monkeypatch.setenv("MODEL_GATEWAY_URL", "http://127.0.0.1:8800/generate")

    client = build_narrative_client_from_env()

    assert client is not None
    assert client.endpoint == "http://127.0.0.1:8800/narrate"


def test_explicit_narrative_endpoint_overrides_derived_url(monkeypatch) -> None:
    monkeypatch.setenv("MODEL_GATEWAY_PROVIDER", "contract_http")
    monkeypatch.setenv("MODEL_GATEWAY_URL", "http://gateway.test/generate")
    monkeypatch.setenv("NARRATIVE_GATEWAY_URL", "http://judge.test/custom")

    client = build_narrative_client_from_env()

    assert client is not None
    assert client.endpoint == "http://judge.test/custom"
