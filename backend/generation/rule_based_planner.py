"""Deterministic dynamic story planner used before a live model is configured."""

from backend.content.context_repository import CharacterDefinitionNotFoundError
from backend.generation.planner import NPCContextProvider
from backend.schemas.content import MemoryItem, NPCGenerationContext
from backend.schemas.game_state import GameState
from backend.schemas.parsed_action import ActionType, ParsedAction
from backend.schemas.player_action import PlayerAction
from backend.schemas.progression import CommitmentItem, QuestItem
from backend.schemas.story import (
    DialogueLine,
    EstablishCommitmentOperation,
    EventProposal,
    OfferQuestOperation,
    SpeakerType,
    StoryProposal,
    TransferItemOperation,
)


class RuleBasedStoryPlanner:
    """Generate state-aware dialogue and proposals without pretending to be AI."""

    def __init__(self, context_provider: NPCContextProvider) -> None:
        self._context_provider = context_provider

    async def propose(
        self,
        action: PlayerAction,
        parsed_action: ParsedAction,
        state: GameState,
    ) -> StoryProposal:
        npc_id = action.target_npc_id or "vidalia"
        try:
            context = await self._context_provider.get_generation_context(
                action.session_id,
                npc_id,
                state.turn_count,
            )
        except CharacterDefinitionNotFoundError:
            return self._missing_character_proposal(action, state, npc_id)

        player_id = state.player.player_id
        npc_name = self._npc_name(context, state)
        message = action.message.strip()
        normalized = message.lower()
        visible_quests = self._visible_player_quests(context, player_id)
        visible_commitments = self._visible_player_commitments(context, player_id)

        intent_summary: str
        text: str
        emotion = "attentive"
        event_proposals: list[EventProposal] = []

        if self._contains_any(normalized, ("任務", "委託", "幫忙", "需要我", "能做什麼")):
            if visible_quests:
                quest = visible_quests[0]
                intent_summary = "承接已保存的任務提議。"
                text = f"先前提到的「{quest.title}」仍然有效。{quest.summary}"
                emotion = "focused"
            elif len(context.active_quests) >= 2:
                intent_summary = "遵守每位 NPC 的進行中任務上限。"
                text = "目前沒有新的公開委託；先讓已經開始的事情往前走。"
                emotion = "measured"
            else:
                intent_summary = "依目前公開場景提出可驗證的觀察任務。"
                text, event = self._offer_observation_quest(
                    context,
                    npc_name,
                    npc_id,
                    player_id,
                    message,
                )
                event_proposals.append(event)
                emotion = "purposeful"
        elif self._contains_any(normalized, ("答應", "承諾", "我會", "我願意")):
            intent_summary = "辨識玩家主動提出的承諾。"
            existing = self._matching_commitment(visible_commitments, message)
            if existing is not None:
                text = f"我記得這項承諾：「{existing.summary}」"
                emotion = "steady"
            elif len(context.active_commitments) >= 3:
                text = "我們已經有幾項承諾尚未完成，先把它們釐清，再談新的約定。"
                emotion = "cautious"
            else:
                text = "我聽見了。承諾會留下痕跡，也應該由說出口的人負責。"
                event_proposals.append(
                    self._establish_player_commitment(
                        npc_id,
                        player_id,
                        message,
                    )
                )
                emotion = "serious"
        elif self._contains_any(normalized, ("給你", "交給你", "贈送", "轉交")):
            intent_summary = "檢查玩家是否明確提出可驗證的物品移轉。"
            item_id = self._mentioned_owned_item(message, state.player.inventory)
            if item_id is None:
                text = "如果你要交付物品，請明確說出物品名稱；我不會把口頭聲稱當成已完成的交付。"
                emotion = "cautious"
            else:
                text = f"我會依實際持有狀態確認你提出的「{item_id}」交付。"
                event_proposals.append(
                    self._transfer_player_item(npc_id, player_id, item_id)
                )
                emotion = "careful"
        elif self._contains_any(normalized, ("記得", "剛才", "之前", "說過")):
            intent_summary = "從該 NPC 的授權互動記憶承接前文。"
            memory = self._latest_player_interaction(context)
            if memory is None:
                text = "我目前沒有更早、可確認的對話記錄；你可以再說一次重點。"
            else:
                text = f"我記得。{memory.content}"
                emotion = "thoughtful"
        elif parsed_action.action_type == ActionType.INSPECT or self._contains_any(
            normalized,
            ("查看", "觀察", "調查", "這裡", "哪裡"),
        ):
            scene_name = str(
                context.public_profile.get("scene_name") or state.current_scene_id
            )
            intent_summary = "使用公開角色資料回應場景觀察。"
            text = (
                f"你目前能確認的是「{scene_name}」。先描述你實際看見的異常，"
                "我不會把尚未查證的推測當成世界事實。"
            )
            emotion = "observant"
        elif self._contains_any(normalized, ("秘密", "真相", "隱瞞")):
            intent_summary = "拒絕從缺失或未授權資料補寫秘密。"
            text = "有些答案目前沒有足夠來源可以確認。我可以談已知的事，但不會把猜測說成真相。"
            emotion = "guarded"
        elif self._contains_any(normalized, ("你好", "嗨", "哈囉", "早安", "晚安")):
            intent_summary = "依回合與既有互動產生招呼回覆。"
            text = self._greeting(state.turn_count, len(context.memories))
            emotion = "welcoming"
        else:
            intent_summary = "依玩家原話與目前狀態產生保守的動態回覆。"
            text = self._generic_reply(message, state.turn_count, bool(context.active_goals))

        return StoryProposal(
            session_id=action.session_id,
            turn_number=state.turn_count + 1,
            intent_summary=intent_summary,
            proposed_dialogue=[
                DialogueLine(
                    speaker_type=SpeakerType.NPC,
                    speaker_id=npc_id,
                    speaker_name=npc_name,
                    text=text,
                    emotion=emotion,
                )
            ],
            event_proposals=event_proposals,
        )

    @staticmethod
    def _npc_name(context: NPCGenerationContext, state: GameState) -> str:
        public_name = context.public_profile.get("name")
        if isinstance(public_name, str) and public_name.strip():
            return public_name
        npc_state = state.npc_states.get(context.npc_id)
        return npc_state.name if npc_state and npc_state.name else context.npc_id

    @staticmethod
    def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _visible_player_quests(
        context: NPCGenerationContext,
        player_id: str,
    ) -> list[QuestItem]:
        return [
            quest
            for quest in context.active_quests
            if quest.visibility == "player"
            and player_id in {quest.giver_id, quest.recipient_id}
        ]

    @staticmethod
    def _visible_player_commitments(
        context: NPCGenerationContext,
        player_id: str,
    ) -> list[CommitmentItem]:
        return [
            commitment
            for commitment in context.active_commitments
            if commitment.visibility == "player"
            and player_id in {commitment.promisor_id, commitment.promisee_id}
        ]

    @staticmethod
    def _matching_commitment(
        commitments: list[CommitmentItem],
        message: str,
    ) -> CommitmentItem | None:
        normalized = message.strip("。！？!? ")
        return next(
            (
                commitment
                for commitment in commitments
                if normalized and normalized in commitment.summary
            ),
            None,
        )

    @staticmethod
    def _latest_player_interaction(context: NPCGenerationContext) -> MemoryItem | None:
        return next(
            (
                memory
                for memory in reversed(context.memories)
                if memory.memory_type == "interaction"
            ),
            None,
        )

    @staticmethod
    def _mentioned_owned_item(message: str, inventory: list[str]) -> str | None:
        lowered = message.lower()
        explicit = next((item for item in inventory if item.lower() in lowered), None)
        if explicit is not None:
            return explicit
        if len(inventory) == 1 and any(word in message for word in ("這個", "這件", "道具")):
            return inventory[0]
        return None

    @staticmethod
    def _greeting(turn_count: int, memory_count: int) -> str:
        if turn_count == 0:
            return "你好，旅人。我在聽；先告訴我你此刻真正想確認的事。"
        if memory_count:
            return "你回來了。我還記得我們先前的交談，這一次想從哪件事繼續？"
        return "又見面了。這個世界不會因一句話改變，但我們可以從可確認的事情開始。"

    @staticmethod
    def _generic_reply(message: str, turn_count: int, has_active_goal: bool) -> str:
        snippet = " ".join(message.split())[:60]
        if has_active_goal:
            return f"我正在處理一件尚未完成的事，也聽見了你提到「{snippet}」。你能再說明你的目的嗎？"
        replies = (
            f"我聽見你提到「{snippet}」。你希望我回應的是事實、看法，還是一項行動？",
            f"關於「{snippet}」，我只能根據目前可確認的狀態回答。你想先釐清哪一部分？",
            f"你的話是「{snippet}」。如果希望世界有所改變，請把要做的事情說得更明確。",
        )
        return replies[(turn_count + len(message)) % len(replies)]

    @staticmethod
    def _offer_observation_quest(
        context: NPCGenerationContext,
        npc_name: str,
        npc_id: str,
        player_id: str,
        player_message: str,
    ) -> tuple[str, EventProposal]:
        scene_name = str(context.public_profile.get("scene_name") or "目前場景")
        title = f"記錄{scene_name}的異常"
        summary = f"在{scene_name}觀察一項可核實的異常，之後向{npc_name}回報。"
        text = f"如果你願意幫忙，請先在{scene_name}記錄一項能被核實的異常，再回來告訴我。"
        return (
            text,
            EventProposal(
                event_type="quest_offered",
                description=f"Rule-based quest proposal triggered by: {player_message[:200]}",
                actor_id=npc_id,
                target_id=player_id,
                operations=[
                    OfferQuestOperation(
                        title=title,
                        summary=summary,
                        giver_id=npc_id,
                        recipient_id=player_id,
                        due_in_turns=5,
                    )
                ],
                witness_ids=[player_id, npc_id],
                visible_to_player=True,
            ),
        )

    @staticmethod
    def _establish_player_commitment(
        npc_id: str,
        player_id: str,
        message: str,
    ) -> EventProposal:
        summary = f"玩家承諾：{message.strip()[:900]}"
        return EventProposal(
            event_type="commitment_created",
            description="Rule-based commitment proposal from the player's explicit wording.",
            actor_id=player_id,
            target_id=npc_id,
            operations=[
                EstablishCommitmentOperation(
                    summary=summary,
                    promisor_id=player_id,
                    promisee_id=npc_id,
                    due_in_turns=5,
                )
            ],
            witness_ids=[player_id, npc_id],
            visible_to_player=True,
        )

    @staticmethod
    def _transfer_player_item(
        npc_id: str,
        player_id: str,
        item_id: str,
    ) -> EventProposal:
        return EventProposal(
            event_type="item_exchange",
            description="Rule-based transfer proposal for an explicitly named owned item.",
            actor_id=player_id,
            target_id=npc_id,
            operations=[
                TransferItemOperation(
                    item_id=item_id,
                    from_entity_id=player_id,
                    to_entity_id=npc_id,
                )
            ],
            witness_ids=[player_id, npc_id],
            visible_to_player=True,
        )

    @staticmethod
    def _missing_character_proposal(
        action: PlayerAction,
        state: GameState,
        npc_id: str,
    ) -> StoryProposal:
        npc_state = state.npc_states.get(npc_id)
        speaker_name = npc_state.name if npc_state and npc_state.name else npc_id
        return StoryProposal(
            session_id=action.session_id,
            turn_number=state.turn_count + 1,
            intent_summary="角色設定缺失，拒絕自行補寫核心資料。",
            proposed_dialogue=[
                DialogueLine(
                    speaker_type=SpeakerType.NPC,
                    speaker_id=npc_id,
                    speaker_name=speaker_name,
                    text="我的角色資料目前還不完整；在正式設定補齊前，我不會自行編造答案。",
                    emotion="reserved",
                )
            ],
            event_proposals=[],
        )
