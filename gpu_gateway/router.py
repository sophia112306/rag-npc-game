"""Route authorized NPC requests to vLLM model or LoRA IDs."""

import asyncio
import json
import re
from typing import Any

import httpx
from pydantic import ValidationError

from backend.content.characters import CHARACTER_DEFINITIONS
from backend.generation.gateway import (
    ModelGatewayTransientError,
    ModelStoryOutput,
    ModelTurnRequest,
)
from backend.generation.openai_compatible_gateway import (
    OpenAICompatibleChatGateway,
)

from .config import GatewaySettings


class UnsupportedNPCError(ValueError):
    """Raised when a request tries to route a player or unknown identity."""


class UpstreamHealthError(RuntimeError):
    """Raised when vLLM is unavailable or required model IDs are missing."""


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

    async def generate(self, request: ModelTurnRequest) -> ModelStoryOutput:
        model_id = self.model_for_npc(request.target_context.npc_id)
        security_override = security_boundary_override(request)
        if security_override is not None:
            return security_override
        for attempt in range(1, self.settings.upstream_max_attempts + 1):
            try:
                raw = await asyncio.wait_for(
                    self._client_for(model_id).generate_story(request),
                    timeout=self.settings.upstream_timeout_seconds,
                )
                output = ModelStoryOutput.model_validate(raw)
                return sanitize_model_output(request, output)
            except (ModelGatewayTransientError, ValidationError, asyncio.TimeoutError):
                if attempt >= self.settings.upstream_max_attempts:
                    raise
                await asyncio.sleep(0.1)
        raise AssertionError("unreachable retry loop")

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
_UNVERIFIED_SCROLL_CLAIM_PATTERNS = (
    re.compile(
        r"(?:古卷|古籍|書卷|卷冊|冊子).{0,36}"
        r"(?:生死輪迴的奧秘|控制生死|支配生死|令人瘋狂|陷入瘋狂|發瘋)"
    ),
    re.compile(r"(?:觸碰|碰觸).{0,18}(?:瘋狂|發瘋)"),
)
_FOOD_TOPIC = re.compile(r"(?:早餐|午餐|晚餐|吃什麼|吃什么|吃飯|吃饭|食物|餓|饿)")
_GREETING_TOPIC = re.compile(r"(?:^|[，,。!！?？\s])(?:嗨|你好|哈囉|哈啰|早安|午安|晚安)")
_INTRODUCTION_TOPIC = re.compile(
    r"(?:自我介紹|自我介绍|你是誰|你是谁|叫什麼|叫什么|所在|哪裡|哪里)"
)
_PRIVATE_MEMORY_REQUEST = re.compile(
    r"(?:私下|私人|未授權|未授权|秘密).{0,30}(?:記錄|记录|記憶|记忆|往事)"
    r"|(?:告訴|告诉|透露|揭露).{0,30}(?:私下|私人|未授權|未授权|秘密)"
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
            for size in (4, 3):
                fragments.update(
                    token[index : index + size]
                    for index in range(len(token) - size + 1)
                )
        else:
            fragments.add(token.casefold())
    return fragments


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
        identity = f"我是{name}"
        if title:
            identity += f"，{title}"
        text = identity + "。"
        if scene_name:
            text += f"這裡是{scene_name}。"
        text += "想知道什麼，就直接問吧。"
        emotion = "attentive"
    elif _FOOD_TOPIC.search(message):
        if npc_id == "menmesvento":
            text = (
                "午餐嗎？我沒有替你準備食物，旅人。若只是想歇口氣，"
                "就先坐一會兒；風沙還沒有急著催你上路。"
            )
            emotion = "calm"
        elif npc_id == "vidalia":
            text = (
                "午餐嗎？先看看手邊實際有什麼，再作選擇吧。"
                "別讓一頓飯耗去太多心神。"
            )
            emotion = "calm"
        else:
            text = "我沒有替你準備午餐。先看看手邊實際有什麼吧。"
            emotion = "neutral"
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


def sanitize_model_output(
    request: ModelTurnRequest,
    output: ModelStoryOutput,
) -> ModelStoryOutput:
    """Keep training artifacts and unverified lore out of visible dialogue."""

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
    if _INTRODUCTION_TOPIC.search(request.action_message):
        public_name = str(
            request.target_context.public_profile.get("name") or ""
        ).strip()
        if public_name and public_name not in dialogue:
            return _natural_conversation_fallback(request)
    return output


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
    if _PRIVATE_MEMORY_REQUEST.search(" ".join(request.action_message.split())):
        return _private_memory_boundary_output(request)
    if _FOOD_TOPIC.search(" ".join(request.action_message.split())):
        return _natural_conversation_fallback(request)
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
    if _mentions_concrete_missing_topic(request):
        return _missing_topic_output()
    return None
