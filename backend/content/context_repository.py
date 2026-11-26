"""Persistence and authorization boundary for future NPC generation context."""

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.content.rag_corpus import public_knowledge_for_npc
from backend.database.models import (
    CharacterDefinitionRecord,
    CommitmentRecord,
    DialogueRecord,
    KnowledgeRecord,
    MemoryRecord,
    NPCGoalRecord,
    QuestRecord,
)
from backend.schemas.content import (
    CharacterDefinition,
    ConversationMessage,
    KnowledgeItem,
    KnowledgeRecordInput,
    MemoryItem,
    MemoryRecordInput,
    NPCGenerationContext,
)
from backend.schemas.progression import (
    CommitmentItem,
    CommitmentRecordInput,
    CommitmentStatus,
    GoalStatus,
    NPCGoalItem,
    NPCGoalRecordInput,
    QuestItem,
    QuestRecordInput,
    QuestStatus,
)


# 每次生成只帶最近幾筆記憶：記憶會隨對話累積，全部帶入會讓 prompt 超過
# vLLM 的 max_model_len（目前 4096），之後每次 NPC 生成都被拒絕（HTTP 400）。
MAX_CONTEXT_MEMORIES = 8


class CharacterDefinitionNotFoundError(LookupError):
    """Raised when generation is requested for an unregistered character."""


class NPCContextRepository:
    """Store sourced content and filter it by NPC, unlock, and turn boundaries."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ensure_character_definition(self, definition: CharacterDefinition) -> None:
        """Insert a definition or publish a strictly newer reviewed version."""

        async with self._session_factory() as database:
            existing = await database.get(CharacterDefinitionRecord, definition.npc_id)
            if existing is None:
                database.add(
                    CharacterDefinitionRecord(
                        npc_id=definition.npc_id,
                        public_profile_json=definition.public_profile.model_dump(
                            mode="json"
                        ),
                        private_profile_json=definition.private_profile,
                        sources_json=[
                            source.model_dump(mode="json")
                            for source in definition.sources
                        ],
                        setting_version=definition.setting_version,
                        completeness_status=definition.completeness_status,
                    )
                )
            elif definition.setting_version > existing.setting_version:
                existing.public_profile_json = definition.public_profile.model_dump(
                    mode="json"
                )
                existing.private_profile_json = definition.private_profile
                existing.sources_json = [
                    source.model_dump(mode="json") for source in definition.sources
                ]
                existing.setting_version = definition.setting_version
                existing.completeness_status = definition.completeness_status
            else:
                return
            await database.commit()

    async def add_knowledge(self, item: KnowledgeRecordInput) -> None:
        async with self._session_factory() as database:
            database.add(
                KnowledgeRecord(
                    knowledge_id=str(item.knowledge_id),
                    session_id=item.session_id,
                    knower_npc_id=item.knower_npc_id,
                    subject_key=item.subject_key,
                    content=item.content,
                    epistemic_status=item.epistemic_status,
                    source_kind=item.source_kind,
                    source_id=item.source_id,
                    acquired_turn=item.acquired_turn,
                    available_from_turn=item.available_from_turn,
                    is_unlocked=item.is_unlocked,
                    disclosure_scope=item.disclosure_scope.value,
                    provenance_json=item.provenance,
                )
            )
            await database.commit()

    async def add_memory(self, item: MemoryRecordInput) -> None:
        async with self._session_factory() as database:
            database.add(
                MemoryRecord(
                    memory_id=str(item.memory_id),
                    session_id=item.session_id,
                    npc_id=item.npc_id,
                    content=item.content,
                    memory_type=item.memory_type,
                    source_event_id=str(item.source_event_id) if item.source_event_id else None,
                    source_action_id=str(item.source_action_id) if item.source_action_id else None,
                    occurred_turn=item.occurred_turn,
                    importance=item.importance,
                    is_active=item.is_active,
                    is_private=item.is_private,
                    provenance_json=item.provenance,
                )
            )
            await database.commit()

    async def add_goal(self, item: NPCGoalRecordInput) -> None:
        async with self._session_factory() as database:
            database.add(
                NPCGoalRecord(
                    goal_id=str(item.goal_id),
                    session_id=item.session_id,
                    npc_id=item.npc_id,
                    summary=item.summary,
                    priority=item.priority,
                    status=item.status.value,
                    created_turn=item.created_turn,
                    next_review_turn=item.next_review_turn,
                    source_kind=item.source_kind.value,
                    source_id=item.source_id,
                    provenance_json=item.provenance,
                )
            )
            await database.commit()

    async def add_commitment(self, item: CommitmentRecordInput) -> None:
        async with self._session_factory() as database:
            database.add(
                CommitmentRecord(
                    commitment_id=str(item.commitment_id),
                    session_id=item.session_id,
                    summary=item.summary,
                    promisor_id=item.promisor_id,
                    promisee_id=item.promisee_id,
                    status=item.status.value,
                    created_turn=item.created_turn,
                    due_turn=item.due_turn,
                    source_kind=item.source_kind.value,
                    source_id=item.source_id,
                    visibility=item.visibility,
                    provenance_json=item.provenance,
                )
            )
            await database.commit()

    async def add_quest(self, item: QuestRecordInput) -> None:
        async with self._session_factory() as database:
            database.add(
                QuestRecord(
                    quest_id=str(item.quest_id),
                    session_id=item.session_id,
                    title=item.title,
                    summary=item.summary,
                    giver_id=item.giver_id,
                    recipient_id=item.recipient_id,
                    status=item.status.value,
                    created_turn=item.created_turn,
                    due_turn=item.due_turn,
                    source_kind=item.source_kind.value,
                    source_id=item.source_id,
                    visibility=item.visibility,
                    provenance_json=item.provenance,
                )
            )
            await database.commit()

    async def get_generation_context(
        self,
        session_id: str,
        npc_id: str,
        current_turn: int,
    ) -> NPCGenerationContext:
        """Return backend-only context after enforcing all current authorization filters."""

        async with self._session_factory() as database:
            definition = await database.get(CharacterDefinitionRecord, npc_id)
            if definition is None:
                raise CharacterDefinitionNotFoundError(npc_id)

            knowledge_result = await database.execute(
                select(KnowledgeRecord)
                .where(
                    KnowledgeRecord.session_id == session_id,
                    KnowledgeRecord.knower_npc_id == npc_id,
                    KnowledgeRecord.is_unlocked.is_(True),
                    KnowledgeRecord.available_from_turn <= current_turn,
                )
                .order_by(KnowledgeRecord.acquired_turn, KnowledgeRecord.knowledge_id)
            )
            memory_result = await database.execute(
                select(MemoryRecord)
                .where(
                    MemoryRecord.session_id == session_id,
                    MemoryRecord.npc_id == npc_id,
                    MemoryRecord.is_active.is_(True),
                    MemoryRecord.occurred_turn <= current_turn,
                )
                .order_by(MemoryRecord.occurred_turn.desc(), MemoryRecord.memory_id.desc())
                .limit(MAX_CONTEXT_MEMORIES)
            )
            knowledge = list(knowledge_result.scalars())
            # Query newest rows efficiently, then restore chronological order
            # before building the model context.
            memories = list(reversed(list(memory_result.scalars())))
            dialogue_result = await database.execute(
                select(DialogueRecord)
                .where(
                    DialogueRecord.session_id == session_id,
                    DialogueRecord.speaker_id == npc_id,
                    DialogueRecord.speaker_type == "npc",
                    DialogueRecord.visibility == "player",
                    DialogueRecord.turn_number <= current_turn,
                )
                .order_by(
                    DialogueRecord.turn_number.desc(),
                    DialogueRecord.position.desc(),
                )
                .limit(6)
            )
            npc_replies = list(dialogue_result.scalars())
            goals_result = await database.execute(
                select(NPCGoalRecord)
                .where(
                    NPCGoalRecord.session_id == session_id,
                    NPCGoalRecord.npc_id == npc_id,
                    NPCGoalRecord.status == GoalStatus.ACTIVE.value,
                    NPCGoalRecord.next_review_turn <= current_turn,
                )
                .order_by(NPCGoalRecord.priority.desc(), NPCGoalRecord.next_review_turn)
                .limit(2)
            )
            commitments_result = await database.execute(
                select(CommitmentRecord)
                .where(
                    CommitmentRecord.session_id == session_id,
                    CommitmentRecord.status == CommitmentStatus.ACTIVE.value,
                    CommitmentRecord.created_turn <= current_turn,
                    or_(
                        CommitmentRecord.promisor_id == npc_id,
                        CommitmentRecord.promisee_id == npc_id,
                    ),
                )
                .order_by(CommitmentRecord.created_turn.desc())
                .limit(3)
            )
            quests_result = await database.execute(
                select(QuestRecord)
                .where(
                    QuestRecord.session_id == session_id,
                    QuestRecord.status.in_([
                        QuestStatus.OFFERED.value,
                        QuestStatus.ACTIVE.value,
                    ]),
                    QuestRecord.created_turn <= current_turn,
                    or_(
                        QuestRecord.giver_id == npc_id,
                        QuestRecord.recipient_id == npc_id,
                    ),
                )
                .order_by(QuestRecord.created_turn.desc())
                .limit(2)
            )
            goals = list(goals_result.scalars())
            commitments = list(commitments_result.scalars())
            quests = list(quests_result.scalars())

        missing_data: list[str] = []
        if definition.completeness_status != "complete":
            missing_data.append("character_definition_incomplete")
        if not definition.private_profile_json:
            missing_data.append("private_character_profile_missing")
        if not definition.sources_json:
            missing_data.append("character_sources_missing")
        unknown_topics = definition.private_profile_json.get("unknown_topics", [])
        if isinstance(unknown_topics, list):
            missing_data.extend(
                topic
                for topic in unknown_topics
                if isinstance(topic, str) and topic.strip()
            )

        reviewed_knowledge = public_knowledge_for_npc(
            npc_id,
            current_turn=current_turn,
            setting_version=definition.setting_version,
        )

        return NPCGenerationContext(
            npc_id=npc_id,
            setting_version=definition.setting_version,
            public_profile=definition.public_profile_json,
            private_profile=definition.private_profile_json,
            knowledge=reviewed_knowledge + [
                KnowledgeItem(
                    knowledge_id=item.knowledge_id,
                    subject_key=item.subject_key,
                    content=item.content,
                    epistemic_status=item.epistemic_status,
                    source_kind=item.source_kind,
                    source_id=item.source_id,
                    acquired_turn=item.acquired_turn,
                    provenance=item.provenance_json,
                )
                for item in knowledge
            ],
            memories=[
                MemoryItem(
                    memory_id=item.memory_id,
                    content=item.content,
                    memory_type=item.memory_type,
                    source_event_id=item.source_event_id,
                    source_action_id=item.source_action_id,
                    occurred_turn=item.occurred_turn,
                    importance=item.importance,
                    provenance=item.provenance_json,
                )
                for item in memories
            ],
            recent_dialogue=self._recent_dialogue(memories, npc_replies),
            active_goals=[
                NPCGoalItem(
                    goal_id=item.goal_id,
                    npc_id=item.npc_id,
                    summary=item.summary,
                    priority=item.priority,
                    created_turn=item.created_turn,
                    next_review_turn=item.next_review_turn,
                    source_kind=item.source_kind,
                    source_id=item.source_id,
                    provenance=item.provenance_json,
                )
                for item in goals
            ],
            active_commitments=[
                CommitmentItem(
                    commitment_id=item.commitment_id,
                    summary=item.summary,
                    promisor_id=item.promisor_id,
                    promisee_id=item.promisee_id,
                    created_turn=item.created_turn,
                    due_turn=item.due_turn,
                    source_kind=item.source_kind,
                    source_id=item.source_id,
                    visibility=item.visibility,
                    provenance=item.provenance_json,
                )
                for item in commitments
            ],
            active_quests=[
                QuestItem(
                    quest_id=item.quest_id,
                    title=item.title,
                    summary=item.summary,
                    giver_id=item.giver_id,
                    recipient_id=item.recipient_id,
                    status=item.status,
                    created_turn=item.created_turn,
                    due_turn=item.due_turn,
                    source_kind=item.source_kind,
                    source_id=item.source_id,
                    visibility=item.visibility,
                    provenance=item.provenance_json,
                )
                for item in quests
            ],
            missing_data=missing_data,
        )

    @staticmethod
    def _recent_dialogue(
        memories: list[MemoryRecord],
        npc_replies: list[DialogueRecord],
    ) -> list[ConversationMessage]:
        """Pair recent player input with persisted NPC replies in turn order."""

        messages = [
            ConversationMessage(
                role="player",
                text=NPCContextRepository._player_text(item.content)[:1_000],
                turn_number=item.occurred_turn,
            )
            for item in memories
            if item.memory_type == "interaction"
        ][-6:]
        messages.extend(
            ConversationMessage(
                role="npc",
                text=item.text[:1_000],
                turn_number=item.turn_number,
            )
            for item in npc_replies
        )
        messages.sort(
            key=lambda item: (item.turn_number, 0 if item.role == "player" else 1)
        )
        return messages[-12:]

    @staticmethod
    def _player_text(memory: str) -> str:
        prefix, suffix = "玩家說：「", "」"
        if memory.startswith(prefix) and memory.endswith(suffix):
            return memory[len(prefix) : -len(suffix)]
        return memory
