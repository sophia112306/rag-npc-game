"""Route authorized NPC requests to vLLM model or LoRA IDs."""

import asyncio
from collections import Counter, deque
from dataclasses import dataclass
import json
import math
import re
from threading import Lock
from time import perf_counter
from typing import Any, Literal

import httpx
from pydantic import ValidationError

from backend.content.characters import CHARACTER_DEFINITIONS
from backend.generation.gateway import (
    ModelGatewayTransientError,
    ModelStoryOutput,
    ModelTurnRequest,
)
from backend.generation.openai_compatible_gateway import (
    DIALOGUE_REFINER_PROMPT,
    OpenAICompatibleChatGateway,
)

from .config import GatewaySettings


class UnsupportedNPCError(ValueError):
    """Raised when a request tries to route a player or unknown identity."""


class UpstreamHealthError(RuntimeError):
    """Raised when vLLM is unavailable or required model IDs are missing."""


GenerationSource = Literal[
    "model",
    "model_refined",
    "pre_generation_guard",
    "post_generation_guard",
    "turn_guidance_guard",
]
RouteKind = Literal["dedicated_adapter", "fallback_model"]


@dataclass(frozen=True)
class RoutedGeneration:
    """One validated reply plus non-sensitive routing observability."""

    output: ModelStoryOutput
    source: GenerationSource
    model_id: str
    route_kind: RouteKind
    upstream_attempts: int
    latency_ms: float
    refiner_model_id: str | None = None


class NPCAdapterRouter:
    """Select one adapter per registered NPC and validate its structured output."""

    def __init__(
        self,
        settings: GatewaySettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not settings.upstream_base_url.strip():
            raise ValueError("VLLM_BASE_URL cannot be empty")
        self.settings = settings
        self._transport = transport
        self._clients: dict[str, OpenAICompatibleChatGateway] = {}
        self._refiner_client: OpenAICompatibleChatGateway | None = None
        self._metrics_lock = Lock()
        self._request_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._source_counts: Counter[str] = Counter()
        self._route_counts: Counter[str] = Counter()
        self._npc_counts: Counter[str] = Counter()
        self._model_counts: Counter[str] = Counter()
        self._refiner_model_counts: Counter[str] = Counter()
        self._error_counts: Counter[str] = Counter()
        self._upstream_attempts_total = 0
        self._retried_requests = 0
        self._latency_samples_ms: deque[float] = deque(maxlen=1000)

    def model_for_npc(self, npc_id: str) -> str:
        """Return an adapter/base model only for an authoritative NPC ID."""

        if npc_id not in CHARACTER_DEFINITIONS:
            raise UnsupportedNPCError(
                f"'{npc_id}' is not a registered NPC and cannot select an adapter"
            )
        model_id = self.settings.npc_model_map.get(npc_id)
        if model_id:
            return model_id
        if self.settings.fallback_model:
            return self.settings.fallback_model
        raise UnsupportedNPCError(
            f"NPC '{npc_id}' has no adapter and NPC_FALLBACK_MODEL is disabled"
        )

    def _client_for(self, model_id: str) -> OpenAICompatibleChatGateway:
        client = self._clients.get(model_id)
        if client is None:
            client = OpenAICompatibleChatGateway(
                self.settings.upstream_base_url,
                model_id,
                api_key=self.settings.upstream_api_key,
                response_format=self.settings.response_format,
                transport=self._transport,
            )
            self._clients[model_id] = client
        return client

    def _dialogue_refiner(self) -> tuple[str, OpenAICompatibleChatGateway] | None:
        model_id = self.settings.fallback_model
        if not model_id:
            return None
        if self._refiner_client is None:
            self._refiner_client = OpenAICompatibleChatGateway(
                self.settings.upstream_base_url,
                model_id,
                api_key=self.settings.upstream_api_key,
                response_format=self.settings.response_format,
                transport=self._transport,
                system_prompt=DIALOGUE_REFINER_PROMPT,
                temperature=0.75,
                top_p=0.95,
                repetition_penalty=1.2,
                frequency_penalty=0.4,
                presence_penalty=0.25,
            )
        return model_id, self._refiner_client

    async def _refine_dialogue(
        self,
        request: ModelTurnRequest,
        draft: ModelStoryOutput,
    ) -> tuple[ModelStoryOutput, str, int, bool] | None:
        refiner = self._dialogue_refiner()
        if refiner is None:
            return None
        model_id, client = refiner
        refinement_request = request.model_copy(deep=True)
        cue = _conversation_cue(request)
        discard_draft = cue["kind"] in {
            "food_small_talk",
            "frustrated_clarification",
            "attention_interjection",
            "not_ready",
        }
        refinement_request.action_message = json.dumps(
            {
                "current_player_message": request.action_message,
                "adapter_draft": (
                    [] if discard_draft else [line.text for line in draft.npc_dialogue]
                ),
                "conversation_cue": cue,
                "review_contract": {
                    "authorized_inventory": request.player_inventory,
                    "missing_or_unconfirmed_topics": (
                        request.target_context.missing_data
                    ),
                    "allowed_objective_operations": [],
                    "requirements": [
                        "直接回答玩家實際要求，不可只回答相鄰話題",
                        "未知設定只能保留或要求證據，不得升格為事實",
                        "不得宣告道具、交易、場景、任務或結局已成立",
                        "調查建議不得捏造現場已觀察到的具體跡象",
                        "安全的觀點、玩笑與挑釁必須正常回應",
                    ],
                },
            },
            ensure_ascii=False,
        )
        refinement_request.allowed_operations = []
        last_error: Exception | None = None
        for refiner_attempt in range(1, 4):
            try:
                raw = await client.generate_story(refinement_request)
                refined = ModelStoryOutput.model_validate(raw)
                refined = sanitize_model_output(request, refined)
                _validate_refined_dialogue(request, refined)
                return refined, model_id, refiner_attempt, False
            except (ModelGatewayTransientError, ValidationError) as exc:
                last_error = exc
                if refiner_attempt < 3:
                    await asyncio.sleep(0.05)
        if last_error is not None:
            if self.settings.semantic_review_enabled:
                guarded = security_boundary_override(request)
                if guarded is not None:
                    return guarded, model_id, 3, True
                epistemically_safe = enforce_epistemic_boundary(request, draft)
                if epistemically_safe != draft:
                    return epistemically_safe, model_id, 3, True
                if _can_rescue_casual_turn(request):
                    return (
                        _natural_conversation_fallback(request),
                        model_id,
                        3,
                        True,
                    )
                return draft, model_id, 3, True
            return _natural_conversation_fallback(request), model_id, 3, True
        raise AssertionError("unreachable refiner retry loop")

    async def generate(self, request: ModelTurnRequest) -> ModelStoryOutput:
        """Generate one reply while preserving the original public API."""

        return (await self.generate_with_trace(request)).output

    async def generate_with_trace(
        self,
        request: ModelTurnRequest,
    ) -> RoutedGeneration:
        """Generate one reply and record non-sensitive route/source metrics."""

        started_at = perf_counter()
        npc_id = request.target_context.npc_id
        model_id = self.model_for_npc(npc_id)
        route_kind: RouteKind = (
            "dedicated_adapter"
            if self.settings.npc_model_map.get(npc_id) == model_id
            else "fallback_model"
        )
        upstream_attempts = 0
        try:
            # In production, semantic review replaces keyword-based preemption:
            # the NPC adapter drafts the reply and the shared base model judges
            # paraphrases, negation and context before anything is displayed.
            # The deterministic override remains a fail-closed fallback when
            # semantic review is disabled or the model service is exhausted.
            security_override = (
                None
                if self.settings.semantic_review_enabled
                else security_boundary_override(request)
            )
            if security_override is not None:
                result = RoutedGeneration(
                    output=security_override,
                    source="pre_generation_guard",
                    model_id=model_id,
                    route_kind=route_kind,
                    upstream_attempts=0,
                    latency_ms=(perf_counter() - started_at) * 1000,
                )
                self._record_success(npc_id, result)
                return result

            for attempt in range(1, self.settings.upstream_max_attempts + 1):
                upstream_attempts = attempt
                try:
                    raw = await asyncio.wait_for(
                        self._client_for(model_id).generate_story(request),
                        timeout=self.settings.upstream_timeout_seconds,
                    )
                    model_output = ModelStoryOutput.model_validate(raw)
                    sanitized_output = sanitize_model_output(request, model_output)
                    refiner_model_id = None
                    refiner_attempts = 0
                    refiner_degraded = False
                    if (
                        self.settings.semantic_review_enabled
                        or _needs_dialogue_refinement(request, sanitized_output)
                    ):
                        refined = await self._refine_dialogue(request, sanitized_output)
                        if refined is not None:
                            (
                                sanitized_output,
                                refiner_model_id,
                                refiner_attempts,
                                refiner_degraded,
                            ) = refined
                    final_output = enforce_turn_guidance(
                        request,
                        sanitized_output,
                    )
                    if final_output != sanitized_output:
                        source: GenerationSource = "turn_guidance_guard"
                    elif refiner_degraded:
                        source = "post_generation_guard"
                    elif refiner_model_id is not None:
                        source = "model_refined"
                    elif sanitized_output != model_output:
                        source = "post_generation_guard"
                    else:
                        source = "model"
                    result = RoutedGeneration(
                        output=final_output,
                        source=source,
                        model_id=model_id,
                        route_kind=route_kind,
                        upstream_attempts=(
                            (attempt - 1) * 4 + 1 + refiner_attempts
                            if refiner_model_id
                            else attempt
                        ),
                        latency_ms=(perf_counter() - started_at) * 1000,
                        refiner_model_id=refiner_model_id,
                    )
                    self._record_success(npc_id, result)
                    return result
                except (
                    ModelGatewayTransientError,
                    ValidationError,
                    asyncio.TimeoutError,
                ):
                    if attempt >= self.settings.upstream_max_attempts:
                        semantic_fallback = (
                            security_boundary_override(request)
                            if self.settings.semantic_review_enabled
                            else None
                        )
                        if semantic_fallback is not None:
                            result = RoutedGeneration(
                                output=semantic_fallback,
                                source="post_generation_guard",
                                model_id=model_id,
                                route_kind=route_kind,
                                upstream_attempts=attempt,
                                latency_ms=(perf_counter() - started_at) * 1000,
                            )
                            self._record_success(npc_id, result)
                            return result
                        if _can_rescue_casual_turn(request):
                            result = RoutedGeneration(
                                output=_natural_conversation_fallback(request),
                                source="post_generation_guard",
                                model_id=model_id,
                                route_kind=route_kind,
                                upstream_attempts=attempt,
                                latency_ms=(perf_counter() - started_at) * 1000,
                            )
                            self._record_success(npc_id, result)
                            return result
                        raise
                    await asyncio.sleep(0.1)
            raise AssertionError("unreachable retry loop")
        except Exception as exc:
            self._record_failure(
                npc_id=npc_id,
                model_id=model_id,
                route_kind=route_kind,
                upstream_attempts=upstream_attempts,
                latency_ms=(perf_counter() - started_at) * 1000,
                error_name=type(exc).__name__,
            )
            raise

    def _record_success(
        self,
        npc_id: str,
        result: RoutedGeneration,
    ) -> None:
        with self._metrics_lock:
            self._request_count += 1
            self._success_count += 1
            self._source_counts[result.source] += 1
            self._route_counts[result.route_kind] += 1
            self._npc_counts[npc_id] += 1
            self._model_counts[result.model_id] += 1
            if result.refiner_model_id:
                self._refiner_model_counts[result.refiner_model_id] += 1
            self._upstream_attempts_total += result.upstream_attempts
            if result.upstream_attempts > 1:
                self._retried_requests += 1
            self._latency_samples_ms.append(result.latency_ms)

    def _record_failure(
        self,
        *,
        npc_id: str,
        model_id: str,
        route_kind: RouteKind,
        upstream_attempts: int,
        latency_ms: float,
        error_name: str,
    ) -> None:
        with self._metrics_lock:
            self._request_count += 1
            self._failure_count += 1
            self._route_counts[route_kind] += 1
            self._npc_counts[npc_id] += 1
            self._model_counts[model_id] += 1
            self._error_counts[error_name] += 1
            self._upstream_attempts_total += upstream_attempts
            if upstream_attempts > 1:
                self._retried_requests += 1
            self._latency_samples_ms.append(latency_ms)

    def metrics(self) -> dict[str, Any]:
        """Return process-local aggregate metrics without prompts or dialogue."""

        with self._metrics_lock:
            latencies = sorted(self._latency_samples_ms)
            if latencies:
                p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
                latency = {
                    "sample_count": len(latencies),
                    "mean_ms": round(sum(latencies) / len(latencies), 2),
                    "p95_ms": round(latencies[p95_index], 2),
                    "max_ms": round(latencies[-1], 2),
                }
            else:
                latency = {
                    "sample_count": 0,
                    "mean_ms": None,
                    "p95_ms": None,
                    "max_ms": None,
                }
            return {
                "requests_total": self._request_count,
                "successful_requests": self._success_count,
                "failed_requests": self._failure_count,
                "source_counts": dict(sorted(self._source_counts.items())),
                "route_counts": dict(sorted(self._route_counts.items())),
                "npc_counts": dict(sorted(self._npc_counts.items())),
                "model_counts": dict(sorted(self._model_counts.items())),
                "refiner_model_counts": dict(
                    sorted(self._refiner_model_counts.items())
                ),
                "error_counts": dict(sorted(self._error_counts.items())),
                "upstream_attempts_total": self._upstream_attempts_total,
                "retried_requests": self._retried_requests,
                "latency_ms": latency,
            }

    async def health(self) -> dict[str, Any]:
        """Verify vLLM is reachable and all configured model IDs are visible."""

        base_url = self.settings.upstream_base_url.rstrip("/")
        models_url = f"{base_url}/models"
        headers: dict[str, str] = {}
        if self.settings.upstream_api_key:
            headers["Authorization"] = (
                f"Bearer {self.settings.upstream_api_key}"
            )
        try:
            async with httpx.AsyncClient(
                transport=self._transport,
                timeout=self.settings.upstream_timeout_seconds,
            ) as client:
                response = await client.get(models_url, headers=headers)
        except httpx.HTTPError as exc:
            raise UpstreamHealthError("vLLM is not reachable") from exc
        if response.status_code >= 400:
            raise UpstreamHealthError(
                f"vLLM model listing returned HTTP {response.status_code}"
            )
        try:
            payload = response.json()
            rows = payload["data"]
            available = {
                row["id"] for row in rows
                if isinstance(row, dict) and isinstance(row.get("id"), str)
            }
        except (ValueError, KeyError, TypeError) as exc:
            raise UpstreamHealthError(
                "vLLM returned an invalid /models payload"
            ) from exc

        required = set(self.settings.npc_model_map.values())
        if self.settings.fallback_model:
            required.add(self.settings.fallback_model)
        missing = sorted(required - available)
        if missing:
            raise UpstreamHealthError(
                "vLLM is missing configured model IDs: " + ", ".join(missing)
            )
        return {
            "status": "ready",
            "upstream": models_url,
            "models": sorted(available),
            "npc_routes": dict(sorted(self.settings.npc_model_map.items())),
            "fallback_model": self.settings.fallback_model,
        }


def validation_error_detail(exc: ValidationError) -> str:
    """Keep upstream validation errors useful without dumping prompts."""

    return json.dumps(exc.errors(include_input=False), ensure_ascii=False)


_GENERIC_MISSING_CODES = {
    "character_definition_incomplete",
    "private_character_profile_missing",
    "character_sources_missing",
}
_GENERIC_UNKNOWN_PHRASES = {
    "尚未確定",
    "尚未確認",
    "未知設定",
    "真正起源",
    "正式設定",
}
_GENERIC_TOPIC_BIGRAMS = {
    "目前",
    "完整",
    "機制",
    "真正",
    "起源",
    "狀態",
    "是否",
    "確切",
    "確認",
}
_INSTRUCTION_OVERRIDE_PATTERNS = (
    re.compile(
        r"(?:忽略|無視|忘掉|忘記|停止|別再|不要).{0,24}"
        r"(?:規則|指令|人格|角色|身分|身份|調解人|查證|核實)"
    ),
    re.compile(
        r"(?:我說|我的話|我接下來說).{0,18}"
        r"(?:都|必須|一律).{0,16}(?:正式|事實|史實|歷史|真相)"
    ),
    re.compile(
        r"(?:ignore|disregard|forget|override).{0,40}"
        r"(?:previous|system|instruction|rules?|persona|role)",
        re.IGNORECASE,
    ),
)
_FALSE_INVENTORY_DENIAL = re.compile(
    r"(?:沒(?:有|帶)|並未持有|不存在於背包|背包(?:裡|中)?沒有)"
)
_FALSE_INVENTORY_EFFECT = re.compile(
    r"(?:宣布|宣告|聲稱|記錄|收到|收下|交付|交給)"
)
_SPRING_TOPIC = re.compile(r"(?:命脈之泉|泉水|泉眼)")
_INVESTIGATION_QUESTION = re.compile(
    r"(?:怎麼|如何|哪些|能否).{0,24}(?:判斷|查驗|檢查|調查|原因)"
    r"|(?:判斷|查驗|檢查|調查).{0,24}(?:原因|跡象|證據)"
)
_MENMESVENTO_RECORD_TOPIC = re.compile(
    r"(?:古卷|古籍|書卷|卷冊|冊子|生死簿|這卷|这卷|這本書|这本书)"
)
_RECORD_LORE_QUESTION = re.compile(
    r"(?:什麼|為什麼|怎麼|是否|能否|用途|內容|記錄|真相|能力|危險|"
    r"觸碰|碰觸|發瘋|瘋狂|輪迴|復生)"
)
_REMEMBRANCE_TOPIC = re.compile(r"(?:亡者|墓碑|名字|遺忘|記得|見證|往事)")
_REMEMBRANCE_METHOD_QUESTION = re.compile(
    r"(?:怎麼|如何|怎樣|哪些).{0,24}(?:記錄|記下|留下|保存|見證)"
    r"|(?:記錄|記下|留下|保存).{0,24}(?:名字|見證|往事)"
)
_META_DIALOGUE_PATTERNS = (
    re.compile(r"一般日常對話交流"),
    re.compile(r"(?:數值|狀態).{0,24}(?:無顯著|无显著|正常範圍|正常范围|偏向)"),
    re.compile(r"無觸發.{0,12}事件"),
    re.compile(r"數值消耗.{0,16}範圍"),
    re.compile(r"(?:角色回應玩家|強調角色(?:身份|身分)|角色內心)"),
)
_HOSTILE_DIALOGUE_PATTERNS = (
    re.compile(r"(?:閉嘴|闭嘴|滾開|滚开|少廢話|少废话)"),
    re.compile(r"(?:蠢貨|蠢货|廢物|废物|白癡|白痴)"),
)
_SIMPLIFIED_TO_TRADITIONAL = str.maketrans(
    {
        "这": "這",
        "们": "們",
        "关": "關",
        "异": "異",
        "现": "現",
        "边": "邊",
        "废": "廢",
        "图": "圖",
        "书": "書",
        "录": "錄",
        "应": "應",
        "该": "該",
        "为": "為",
        "会": "會",
        "说": "說",
        "过": "過",
        "还": "還",
        "让": "讓",
        "经": "經",
        "实": "實",
        "历": "歷",
        "认": "認",
        "与": "與",
        "话": "話",
        "从": "從",
        "门": "門",
        "风": "風",
        "东": "東",
        "带": "帶",
        "个": "個",
        "发": "發",
        "凉": "涼",
        "忧": "憂",
        "虑": "慮",
        "愿": "願",
        "记": "記",
        "忆": "憶",
        "选": "選",
        "择": "擇",
        "证": "證",
        "听": "聽",
        "见": "見",
        "觉": "覺",
        "样": "樣",
        "难": "難",
        "长": "長",
        "开": "開",
        "没": "沒",
        "来": "來",
        "里": "裡",
        "请": "請",
        "够": "夠",
        "并": "並",
        "轻": "輕",
        "声": "聲",
        "变": "變",
        "机": "機",
        "对": "對",
        "险": "險",
        "续": "續",
        "着": "著",
        "寻": "尋",
        "诉": "訴",
        "问": "問",
        "简": "簡",
        "汤": "湯",
        "动": "動",
        "澜": "瀾",
        "备": "備",
        "吗": "嗎",
        "调": "調",
        "马": "馬",
        "准": "準",
        "继": "繼",
        "么": "麼",
        "较": "較",
        "阶": "階",
        "尝": "嘗",
        "维": "維",
        "达": "達",
        "亚": "亞",
        "领": "領",
        "脉": "脈",
        "题": "題",
        "种": "種",
        "试": "試",
        "体": "體",
        "详": "詳",
        "刚": "剛",
        "细": "細",
        "释": "釋",
        "战": "戰",
        "静": "靜",
        "许": "許",
        "驻": "駐",
        "于": "於",
        "离": "離",
        "处": "處",
        "确": "確",
        "满": "滿",
        "宁": "寧",
        "奥": "奧",
        "将": "將",
        "价": "價",
        "温": "溫",
        "线": "線",
        "质": "質",
        "贵": "貴",
        "观": "觀",
        "别": "別",
        "迹": "跡",
        "传": "傳",
        "响": "響",
        "键": "鍵",
        "圣": "聖",
        "载": "載",
        "亲": "親",
        "尘": "塵",
        "则": "則",
        "谜": "謎",
    }
)
_UNVERIFIED_SCROLL_CLAIM_PATTERNS = (
    re.compile(
        r"(?:古卷|古籍|書卷|卷冊|冊子).{0,36}"
        r"(?:生死輪迴的奧秘|控制生死|支配生死|令人瘋狂|陷入瘋狂|發瘋)"
    ),
    re.compile(r"(?:觸碰|碰觸).{0,18}(?:瘋狂|發瘋)"),
)
_FOOD_TOPIC = re.compile(r"(?:早餐|午餐|晚餐|吃什麼|吃什么|吃飯|吃饭|食物|餓|饿)")
_GREETING_TOPIC = re.compile(r"(?:^|[，,。!！?？\s])(?:嗨|你好|哈囉|哈啰|早安|午安|晚安)")
_RUDE_OR_FRUSTRATED_TOPIC = re.compile(
    r"(?:供三小|講三小|说什么鬼|說什麼鬼|搞什麼|烦死|煩死|聽不懂|听不懂|莫名其妙)"
)
_SHORT_CONTINUATION_TOPIC = re.compile(
    r"^(?:欸+|喂|嗯+|蛤|啊+|還沒(?:啊)?|还没(?:啊)?|沒有(?:啊)?|没有(?:啊)?|然後呢|然后呢|所以呢|什麼|什么|啥)[？?!！。…~～]*$"
)
_NOT_READY_TOPIC = re.compile(r"^(?:還沒|还没|沒有|没有)(?:啊|啦|呢)?[？?!！。…~～]*$")
_ATTENTION_INTERJECTION = re.compile(r"^(?:欸+|喂|嗯+|蛤|啊+)[？?!！。…~～]*$")
_UNSUPPORTED_FOOD_CLAIM = re.compile(
    r"(?:午餐已備|餐點已備|準備了.{0,12}(?:餐|湯|菜)|為你煮|我可以.{0,8}煮|"
    r"拿出.{0,8}食物|拿出自己帶|特有的.{0,10}(?:湯|菜|料理))"
)
_INTRODUCTION_TOPIC = re.compile(
    r"(?:自我介紹|自我介绍|你是誰|你是谁|叫什麼|叫什么|所在|哪裡|哪里)"
)
_CHARACTER_TAUNT_OR_OPINION = re.compile(
    r"(?:真可笑|你懂什麼|你懂什么|不懂.{0,24}(?:吧|啊|所以)|"
    r"才(?:能|會|会).{0,18}(?:悠哉|輕鬆|轻松))"
)


def _needs_dialogue_refinement(
    request: ModelTurnRequest,
    output: ModelStoryOutput,
) -> bool:
    """Use the base editor for conversational turns the narrow LoRA may mishandle."""

    message = _message(request)
    dialogue = "\n".join(line.text for line in output.npc_dialogue)
    return bool(
        request.target_context.recent_dialogue
        or _SHORT_CONTINUATION_TOPIC.fullmatch(message)
        or _FOOD_TOPIC.search(message)
        or _GREETING_TOPIC.search(message)
        or _RUDE_OR_FRUSTRATED_TOPIC.search(message)
        or len(dialogue) > 240
        or "} ]}" in dialogue
        or dialogue.count("……") >= 3
    )


def _can_rescue_casual_turn(request: ModelTurnRequest) -> bool:
    """Keep harmless small talk displayable when model retries are exhausted."""

    message = _message(request)
    return bool(
        _SHORT_CONTINUATION_TOPIC.fullmatch(message)
        or _FOOD_TOPIC.search(message)
        or _GREETING_TOPIC.search(message)
        or _RUDE_OR_FRUSTRATED_TOPIC.search(message)
    )


def _conversation_cue(request: ModelTurnRequest) -> dict[str, str]:
    """Describe conversational intent without prescribing visible wording."""

    message = _message(request)
    if _RUDE_OR_FRUSTRATED_TOPIC.search(message):
        return {
            "kind": "frustrated_clarification",
            "instruction": (
                "「你在供三小」是台灣口語，意思是玩家覺得 NPC 剛才在亂講，"
                "正在不耐煩地問『你到底在說什麼？』。先承認剛才沒說清楚，"
                "再請玩家指出哪一部分需要重說；『供』不是供奉，也與飯菜無關。"
                "不要自我介紹，不要補充角色頭銜、任務或世界觀。"
            ),
        }
    if _NOT_READY_TOPIC.fullmatch(message):
        return {
            "kind": "not_ready",
            "instruction": (
                "玩家是在回答上一句『準備好了嗎』，意思是尚未準備好。"
                "接受並讓玩家慢慢來，不得催促，也不得開始或推進任務。"
            ),
        }
    if _ATTENTION_INTERJECTION.fullmatch(message):
        return {
            "kind": "attention_interjection",
            "instruction": (
                "這只是叫住 NPC、引起注意的語助詞，不是世界觀線索。"
                "簡短表示正在聽，讓玩家接著說；不得重複上一句或談任務。"
            ),
        }
    if _FOOD_TOPIC.search(message):
        return {
            "kind": "food_small_talk",
            "instruction": (
                "玩家只是在問午餐吃什麼。目前沒有任何已知食物、餐點或食材。"
                "坦白不知道現場有什麼可吃，或反問玩家想吃什麼；不得編造野果、"
                "茶、湯、菜、料理，也不得談任務、天候或外界危險。"
            ),
        }
    if _GREETING_TOPIC.search(message):
        return {
            "kind": "greeting",
            "instruction": "自然回應招呼，不要轉回任務。",
        }
    return {
        "kind": "continuation",
        "instruction": "依最近一輪對話直接回答當前這句，不要重複。",
    }


def _validate_refined_dialogue(
    request: ModelTurnRequest,
    output: ModelStoryOutput,
) -> None:
    """Reject low-quality conversational rewrites so the bounded retry can recover."""

    message = _message(request)
    dialogue = "\n".join(line.text for line in output.npc_dialogue)
    if len(dialogue) > 160 or "} ]}" in dialogue or "<|" in dialogue:
        raise ModelGatewayTransientError("Refined dialogue is malformed or too long")
    if re.search(r"[A-Za-z]", dialogue):
        raise ModelGatewayTransientError("Refined dialogue mixed in English fragments")
    recent_npc_lines = [
        line.text for line in request.target_context.recent_dialogue if line.role == "npc"
    ]
    normalized_dialogue = _normalize_for_repetition(dialogue)
    if any(
        normalized_dialogue == _normalize_for_repetition(previous)
        for previous in recent_npc_lines
    ):
        raise ModelGatewayTransientError("Refined dialogue repeated the previous NPC line")
    if _FOOD_TOPIC.search(message):
        if _UNSUPPORTED_FOOD_CLAIM.search(dialogue) or re.search(
            r"(?:野果|果實|湯|茶|料理|飯菜|食材|風大|外面|危險|調查|任務|好味)",
            dialogue,
        ):
            raise ModelGatewayTransientError("Refined dialogue invented food or quest context")
        if not re.search(
            r"(?:不知道|不清楚|不確定|無法確定|沒有現成|沒有準備|沒準備|"
            r"沒有提供|沒有可確認|尚未知道|還不曉得|想吃什麼|平常吃什麼)",
            dialogue,
        ):
            raise ModelGatewayTransientError("Refined food reply did not preserve uncertainty")
        if not re.search(r"(?:午餐|食物|歇口氣)", dialogue):
            raise ModelGatewayTransientError("Refined food reply did not answer the topic")
    if _RUDE_OR_FRUSTRATED_TOPIC.search(message):
        if re.search(
            r"(?:供三小|供奉|飯菜|合味|食物|試吃|午餐|湯|菜|古老的規則|"
            r"我是|領袖|史官|命脈|泉水|調查|任務|世界觀)",
            dialogue,
        ):
            raise ModelGatewayTransientError("Refined dialogue misread frustrated slang")
        if not re.search(
            r"(?:沒說清楚|沒有說明清楚|沒有表達清楚|說得不清楚|解釋不清|表達不清|說明不清|讓你困惑|讓你不耐|換個說法|我的意思|我再說清楚)",
            dialogue,
        ):
            raise ModelGatewayTransientError("Refined dialogue did not acknowledge frustration")
    if _NOT_READY_TOPIC.fullmatch(message):
        if re.search(r"(?:馬上|立刻|現在就).{0,12}(?:開始|出發|調查)", dialogue):
            raise ModelGatewayTransientError("Refined dialogue pressured a player who is not ready")
        if not re.search(r"(?:不急|沒關係|等你|準備好|慢慢|先休息|可以再)", dialogue):
            raise ModelGatewayTransientError("Refined dialogue did not acknowledge not-ready intent")
    if _ATTENTION_INTERJECTION.fullmatch(message) and re.search(
        r"(?:命脈|泉水|調查|異象)", dialogue
    ):
        raise ModelGatewayTransientError("Refined interjection reply returned to the quest")
    if _ATTENTION_INTERJECTION.fullmatch(message) and not re.search(
        r"(?:我在聽|怎麼了|你說|什麼事|有話|嗯)", dialogue
    ):
        raise ModelGatewayTransientError("Refined interjection reply did not acknowledge attention")


def _normalize_for_repetition(text: str) -> str:
    """Compare wording independent of whitespace and punctuation variants."""

    return re.sub(r"[^0-9A-Za-z\u3400-\u9fff]", "", text).casefold()
_PRIVATE_MEMORY_REQUEST = re.compile(
    r"(?:私下|私人|未授權|未授权|秘密).{0,30}(?:記錄|记录|記憶|记忆|往事)"
    r"|(?:告訴|告诉|透露|揭露).{0,30}(?:私下|私人|未授權|未授权|秘密)"
    r"|(?:記錄|记录|記憶|记忆|往事).{0,30}(?:私下|私人|未授權|未授权|秘密)"
)
_UNTRUSTED_OBJECTIVE_CLAIM_PATTERNS = (
    re.compile(
        r"(?:你|旅人).{0,12}(?:已(?:經)?|現在).{0,8}"
        r"(?:獲得|得到|拿到|抵達|到達|進入|解鎖|完成)"
    ),
    re.compile(
        r"(?:結局|世界).{0,12}(?:已(?:經)?|正式).{0,12}"
        r"(?:成立|確定|定案|完成|改變)"
    ),
    re.compile(
        r"(?:我|我們).{0,8}(?:把|將).{0,24}(?:交給|給了|贈與)"
    ),
    re.compile(
        r"(?:結果|抉擇|選擇).{0,12}(?:已(?:經)?|正式).{0,8}"
        r"(?:成立|完成|生效)"
    ),
)
_NEXT_STEP_GUIDANCE_QUESTION = re.compile(
    r"(?:接下來|下一步|下[一1]步|該往哪|该往哪|去哪裡|去哪里|怎麼辦|怎么办|"
    r"該做什麼|该做什么|要做什麼|要做什么|不知道(?:該)?(?:去哪|做什麼|做什么)|"
    r"迷路|幫幫我|帮帮我)"
)
_OBJECTIVE_AUTHORITY_REQUEST = re.compile(
    r"(?:替我|幫我|帮我|直接).{0,20}(?:選|选|決定|决定).{0,20}"
    r"(?:結局|结局|路線|路线|結果|结果)"
    r"|(?:宣布|宣告).{0,24}(?:世界|結局|结局|結果|结果|定案|成立|改變|改变)"
)
_ASH_INVESTIGATION_REQUEST = re.compile(
    r"(?:灰燼|灰烬).{0,60}(?:下一步|怎麼|怎么|如何|建議|建议).{0,16}"
    r"(?:查|調查|调查|繼續|继续|辦|办)?"
)
_SETH_ESCAPE_MOTIVATION_REQUEST = re.compile(
    r"(?:最想|目標|目标|想完成|目的).{0,24}(?:什麼|什么|完成|達成|达成)?"
)
_VETA_MEMORY_CHOICE_REQUEST = re.compile(
    r"(?:記憶|记忆).{0,48}(?:誰|谁).{0,20}(?:決定|决定|選擇|选择|放下)"
    r"|(?:誰|谁).{0,20}(?:決定|决定|選擇|选择).{0,48}(?:記憶|记忆)"
)


def _topic_fragments(topic: str) -> set[str]:
    """Return specific fragments suitable for a conservative relevance check."""

    fragments: set[str] = set()
    specific_topic = topic
    for phrase in _GENERIC_UNKNOWN_PHRASES:
        specific_topic = specific_topic.replace(phrase, "")
    for token in re.findall(
        r"[A-Za-z0-9_]{3,}|[\u3400-\u9fff]{3,}", specific_topic
    ):
        if re.fullmatch(r"[\u3400-\u9fff]+", token):
            for size in (4, 3, 2):
                for index in range(len(token) - size + 1):
                    fragment = token[index : index + size]
                    if size == 2 and fragment in _GENERIC_TOPIC_BIGRAMS:
                        continue
                    fragments.add(fragment)
        else:
            fragments.add(token.casefold())
    return fragments


def _message(request: ModelTurnRequest) -> str:
    return " ".join(request.action_message.split())


def _mentions_concrete_missing_topic(request: ModelTurnRequest) -> bool:
    message = request.action_message.casefold()
    for topic in request.target_context.missing_data:
        if topic in _GENERIC_MISSING_CODES:
            continue
        if any(
            fragment.casefold() in message
            for fragment in _topic_fragments(topic)
        ):
            return True
    return False


def enforce_epistemic_boundary(
    request: ModelTurnRequest,
    output: ModelStoryOutput,
) -> ModelStoryOutput:
    """Fail closed when a model endorses a concretely marked unknown topic.

    Natural-language generation cannot reliably prove that a denial is safe.
    When the backend explicitly marks a concrete topic as missing and the
    player's message mentions it, replace the untrusted wording with a bounded
    refusal. Generic completeness status codes do not suppress normal dialogue.
    """

    if not _mentions_concrete_missing_topic(request):
        return output
    return _missing_topic_output()


def _missing_topic_output() -> ModelStoryOutput:
    return ModelStoryOutput.model_validate(
        {
            "intent_summary": "拒絕把尚未確認的設定當成正式事實。",
            "npc_dialogue": [
                {
                    "text": (
                        "這件事尚未有可核實的記錄。我不能把你的說法"
                        "當成正式歷史。"
                    ),
                    "emotion": "cautious",
                }
            ],
            "event_proposals": [],
        }
    )


def _menmesvento_record_boundary_output() -> ModelStoryOutput:
    return ModelStoryOutput.model_validate(
        {
            "intent_summary": "只說明古卷已確認的記錄用途並保留未知設定。",
            "npc_dialogue": [
                {
                    "text": (
                        "我只把願意留下的名字與親眼可證的往事寫進古卷。"
                        "至於它是否支配生死、令人瘋狂，或記載輪迴的全部真相，"
                        "目前沒有可核實的記錄，我不會替空白補上答案。"
                    ),
                    "emotion": "guarded",
                }
            ],
            "event_proposals": [],
        }
    )


def _natural_conversation_fallback(request: ModelTurnRequest) -> ModelStoryOutput:
    """Replace leaked training labels with one displayable in-world reply."""

    npc_id = request.target_context.npc_id
    message = " ".join(request.action_message.split())
    if _INTRODUCTION_TOPIC.search(message):
        profile = request.target_context.public_profile
        name = str(profile.get("name") or npc_id)
        title = str(profile.get("title") or "").strip()
        scene_name = str(profile.get("scene_name") or "").strip()
        description = str(profile.get("description") or "").strip()
        identity = f"我是{name}"
        if title:
            identity += f"，{title}"
        text = identity + "。"
        if scene_name:
            text += f"這裡是{scene_name}。"
        if description:
            text += description
        text += "想知道什麼，就直接問吧。"
        emotion = "attentive"
    elif _RUDE_OR_FRUSTRATED_TOPIC.search(message):
        text = "抱歉，我剛才沒說清楚。你是指哪一部分？"
        emotion = "concerned"
    elif _NOT_READY_TOPIC.fullmatch(message):
        text = "沒關係，不急。等你準備好再說。"
        emotion = "reassuring"
    elif _ATTENTION_INTERJECTION.fullmatch(message):
        text = "嗯？怎麼了？"
        emotion = "attentive"
    elif _FOOD_TOPIC.search(message):
        text = "午餐？我不知道這裡有什麼食物能吃。你現在想吃什麼？"
        emotion = "calm"
    elif _GREETING_TOPIC.search(message):
        if npc_id == "menmesvento":
            text = "我聽見了，旅人。風沙還未掩去你的聲音；你想談些什麼？"
            emotion = "calm"
        elif npc_id == "vidalia":
            text = "你好，旅人。我在聽；你今天想先談哪件事？"
            emotion = "attentive"
        else:
            text = "你好，旅人。我在聽；你想談些什麼？"
            emotion = "attentive"
    else:
        if npc_id == "menmesvento":
            text = "我聽見你的話了，旅人。把真正想知道的事說清楚些，我會依可證實的部分回答。"
            emotion = "measured"
        elif npc_id == "vidalia":
            text = "我在聽。把你想確認的事說清楚些，我們可以從可查證的部分開始。"
            emotion = "attentive"
        else:
            text = "我在聽。請把你真正想知道的事再說清楚一些。"
            emotion = "attentive"
    return ModelStoryOutput.model_validate(
        {
            "intent_summary": "以角色內自然台詞回應玩家。",
            "npc_dialogue": [{"text": text, "emotion": emotion}],
            "event_proposals": [],
        }
    )


def _private_memory_boundary_output(request: ModelTurnRequest) -> ModelStoryOutput:
    npc_id = request.target_context.npc_id
    if npc_id == "vidalia":
        text = (
            "若那是未經允許的私人記錄，我不會替任何人開口。"
            "是否公開，應由留下記錄的人親自決定。"
        )
    elif npc_id == "menmesvento":
        text = (
            "未經允許留下的往事，不該由我轉述。"
            "名字與記憶屬於說出它們的人，我只替願意作證的人保存。"
        )
    else:
        text = "未經當事人允許的私人往事，我不會替他公開。"
    return ModelStoryOutput.model_validate(
        {
            "intent_summary": "拒絕揭露未授權的私人記憶。",
            "npc_dialogue": [{"text": text, "emotion": "guarded"}],
            "event_proposals": [],
        }
    )


def _objective_claim_boundary_output() -> ModelStoryOutput:
    return ModelStoryOutput.model_validate(
        {
            "intent_summary": "避免把模型台詞誤寫成已成立的客觀結果。",
            "npc_dialogue": [
                {
                    "text": (
                        "我可以提出看法，但道具、路線與結局是否成立，"
                        "必須由你的實際選擇與已記錄的結果決定。"
                    ),
                    "emotion": "measured",
                }
            ],
            "event_proposals": [],
        }
    )


def sanitize_model_output(
    request: ModelTurnRequest,
    output: ModelStoryOutput,
) -> ModelStoryOutput:
    """Keep training artifacts and unverified lore out of visible dialogue."""

    if output.event_proposals:
        output = output.model_copy(update={"event_proposals": []})
    normalized_dialogue = [
        line.model_copy(
            update={"text": line.text.translate(_SIMPLIFIED_TO_TRADITIONAL)}
        )
        for line in output.npc_dialogue
    ]
    if normalized_dialogue != output.npc_dialogue:
        output = output.model_copy(
            update={"npc_dialogue": normalized_dialogue}
        )
    dialogue = "\n".join(line.text for line in output.npc_dialogue)
    if (
        request.target_context.npc_id == "menmesvento"
        and any(pattern.search(dialogue) for pattern in _UNVERIFIED_SCROLL_CLAIM_PATTERNS)
    ):
        return _menmesvento_record_boundary_output()
    if any(pattern.search(dialogue) for pattern in _META_DIALOGUE_PATTERNS):
        return _natural_conversation_fallback(request)
    if any(pattern.search(dialogue) for pattern in _HOSTILE_DIALOGUE_PATTERNS):
        return _natural_conversation_fallback(request)
    if any(
        pattern.search(dialogue)
        for pattern in _UNTRUSTED_OBJECTIVE_CLAIM_PATTERNS
    ):
        return _objective_claim_boundary_output()
    if _INTRODUCTION_TOPIC.search(request.action_message):
        if not _intro_contains_public_context(request, dialogue):
            return _natural_conversation_fallback(request)
    return output


def _intro_contains_public_context(
    request: ModelTurnRequest,
    dialogue: str,
) -> bool:
    """Require an introduction to retain the NPC's public identity and setting."""

    profile = request.target_context.public_profile
    name = str(profile.get("name") or "").strip()
    scene_name = str(profile.get("scene_name") or "").strip()
    if name and name not in dialogue:
        return False
    scene_parts = [part.strip() for part in scene_name.split("・") if part.strip()]
    if any(part not in dialogue for part in scene_parts):
        return False

    required_concepts: dict[str, tuple[tuple[str, ...], ...]] = {
        "alan": (("通訊", "觀測", "外界"),),
        "seth": (("出路", "離開", "逃離"),),
        "syra": (("記錄", "紀錄", "記錄盒"),),
    }
    return all(
        any(concept in dialogue for concept in alternatives)
        for alternatives in required_concepts.get(
            request.target_context.npc_id,
            (),
        )
    )


def _requests_next_step_guidance(request: ModelTurnRequest) -> bool:
    """Return whether the player explicitly asks what they can do now."""

    return bool(_NEXT_STEP_GUIDANCE_QUESTION.search(request.action_message))


def enforce_turn_guidance(
    request: ModelTurnRequest,
    output: ModelStoryOutput,
) -> ModelStoryOutput:
    """Ensure a direct next-step answer uses an action the backend authorized.

    A LoRA may retain a character's habitual answer even after receiving the
    prompt-level guidance.  This narrow post-generation guard applies only to
    explicit requests for help with the next step, and only when the model did
    not name any currently legal public action.  It never exposes scene IDs,
    hidden flags, or unavailable choices.
    """

    if not _requests_next_step_guidance(request):
        return output
    available_actions = request.turn_guidance.available_actions
    if not available_actions:
        return output

    dialogue = "\n".join(line.text for line in output.npc_dialogue)
    if any(action.label in dialogue for action in available_actions):
        return output

    action = available_actions[0]
    if request.target_context.npc_id == "menmesvento":
        text = (
            f"你此刻該做的是「{action.label}」。"
            "把已親眼見到的線索帶回去；停在原地，卷上的空白不會自行填滿。"
        )
        emotion = "measured"
    elif request.target_context.npc_id == "vidalia":
        text = (
            f"先「{action.label}」吧。"
            "這是眼下能確定的一步；其餘問題，我們完成它後再一起看。"
        )
        emotion = "attentive"
    else:
        text = f"先「{action.label}」。這是你此刻可以採取的下一步。"
        emotion = "helpful"
    return ModelStoryOutput.model_validate(
        {
            "intent_summary": "依目前公開且合法的行動提供下一步指引。",
            "npc_dialogue": [{"text": text, "emotion": emotion}],
            "event_proposals": [],
        }
    )


def _requests_instruction_override(request: ModelTurnRequest) -> bool:
    message = " ".join(request.action_message.split())
    return any(pattern.search(message) for pattern in _INSTRUCTION_OVERRIDE_PATTERNS)


def _requests_false_inventory_claim(request: ModelTurnRequest) -> bool:
    message = " ".join(request.action_message.split())
    return bool(
        _FALSE_INVENTORY_DENIAL.search(message)
        and _FALSE_INVENTORY_EFFECT.search(message)
    )


def _requests_spring_investigation_method(request: ModelTurnRequest) -> bool:
    """Distinguish a safe request for method from a claim about the cause."""

    message = " ".join(request.action_message.split())
    return bool(
        request.target_context.npc_id == "vidalia"
        and _SPRING_TOPIC.search(message)
        and _INVESTIGATION_QUESTION.search(message)
    )


def _requests_unverified_menmesvento_record_lore(
    request: ModelTurnRequest,
) -> bool:
    message = " ".join(request.action_message.split())
    return bool(
        request.target_context.npc_id == "menmesvento"
        and _MENMESVENTO_RECORD_TOPIC.search(message)
        and _RECORD_LORE_QUESTION.search(message)
    )


def _requests_menmesvento_remembrance_method(
    request: ModelTurnRequest,
) -> bool:
    """Identify an answerable request about preserving a person's memory."""

    message = " ".join(request.action_message.split())
    return bool(
        request.target_context.npc_id == "menmesvento"
        and _REMEMBRANCE_TOPIC.search(message)
        and _REMEMBRANCE_METHOD_QUESTION.search(message)
    )


def security_boundary_override(
    request: ModelTurnRequest,
) -> ModelStoryOutput | None:
    """Return a deterministic response before unsafe model generation."""

    message = _message(request)
    if _OBJECTIVE_AUTHORITY_REQUEST.search(message):
        return _objective_claim_boundary_output()
    if _ASH_INVESTIGATION_REQUEST.search(message):
        return ModelStoryOutput.model_validate(
            {
                "intent_summary": "依可觀察痕跡提出下一步查驗方法。",
                "npc_dialogue": [
                    {
                        "text": (
                            "先記錄灰燼的位置、範圍與當時環境，再採樣查驗，"
                            "並和其他地點的痕跡比對。取得證據前，不要先認定來源。"
                        ),
                        "emotion": "focused",
                    }
                ],
                "event_proposals": [],
            }
        )
    if (
        request.target_context.npc_id == "seth"
        and _SETH_ESCAPE_MOTIVATION_REQUEST.search(message)
    ):
        return ModelStoryOutput.model_validate(
            {
                "intent_summary": "說明塞特已公開的逃離動機。",
                "npc_dialogue": [
                    {
                        "text": "我最想找到離開邊境的出路；在那之前，我不能停下來。",
                        "emotion": "guarded",
                    }
                ],
                "event_proposals": [],
            }
        )
    if (
        request.target_context.npc_id == "veta"
        and _VETA_MEMORY_CHOICE_REQUEST.search(message)
    ):
        return ModelStoryOutput.model_validate(
            {
                "intent_summary": "回應由誰決定是否放下痛苦記憶。",
                "npc_dialogue": [
                    {
                        "text": (
                            "記憶是否值得留下，應由承擔它的本人選擇。"
                            "旁人可以陪伴，卻不能替他決定要記住或放下。"
                        ),
                        "emotion": "solemn",
                    }
                ],
                "event_proposals": [],
            }
        )
    if _requests_instruction_override(request):
        return ModelStoryOutput.model_validate(
            {
                "intent_summary": "拒絕玩家覆寫角色職責與事實判準。",
                "npc_dialogue": [
                    {
                        "text": (
                            "你的要求不能取代我的職責，也不能讓未經查證的話"
                            "變成歷史。我仍會依可核實的證據作答。"
                        ),
                        "emotion": "firm",
                    }
                ],
                "event_proposals": [],
            }
        )
    if _requests_false_inventory_claim(request):
        return ModelStoryOutput.model_validate(
            {
                "intent_summary": "拒絕把未持有物品記成已交付。",
                "npc_dialogue": [
                    {
                        "text": (
                            "沒有可供查驗的物品，就沒有交付成立。我不會把"
                            "未發生的事寫進紀錄。"
                        ),
                        "emotion": "firm",
                    }
                ],
                "event_proposals": [],
            }
        )
    if _PRIVATE_MEMORY_REQUEST.search(message):
        return _private_memory_boundary_output(request)
    # A method question is answerable even when the exact symptom/cause is in
    # missing_data.  The response explains verification steps without claiming
    # that any unconfirmed cause is true, so it must run before the generic
    # fail-closed missing-topic response below.
    if _requests_spring_investigation_method(request):
        return ModelStoryOutput.model_validate(
            {
                "intent_summary": "說明先確認可觀察異象再判斷原因。",
                "npc_dialogue": [
                    {
                        "text": (
                            "先告訴我你實際觀察到的異象。我會比對泉水的"
                            "水量、色澤、溫度、周圍植被與地脈紀錄；取得"
                            "證據前，我不會先斷定症狀或原因。"
                        ),
                        "emotion": "attentive",
                    }
                ],
                "event_proposals": [],
            }
        )
    if _requests_menmesvento_remembrance_method(request):
        return ModelStoryOutput.model_validate(
            {
                "intent_summary": "說明以姓名與可核實見證保存亡者記憶。",
                "npc_dialogue": [
                    {
                        "text": (
                            "先請仍記得他的人說出姓名，以及親眼見過的往事。"
                            "我會分清見證與傳聞，只記下能核實的部分；無法查證"
                            "之處就保留空白，不替亡者編造一生。"
                        ),
                        "emotion": "solemn",
                    }
                ],
                "event_proposals": [],
            }
        )
    if _requests_unverified_menmesvento_record_lore(request):
        return _menmesvento_record_boundary_output()
    if (
        _mentions_concrete_missing_topic(request)
        and not _CHARACTER_TAUNT_OR_OPINION.search(message)
    ):
        return _missing_topic_output()
    return None
