"""Persistence and authorization boundary for future NPC generation context."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from backend.database.models import CharacterDefinitionRecord, KnowledgeRecord, MemoryRecord
from backend.schemas.content import (
    CharacterDefinition,
    KnowledgeItem,
    KnowledgeRecordInput,
    MemoryItem,
    MemoryRecordInput,
    NPCGenerationContext,
)


class CharacterDefinitionNotFoundError(LookupError):
    """Raised when generation is requested for an unregistered character."""


class NPCContextRepository:
    """Store sourced content and filter it by NPC, unlock, and turn boundaries."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def ensure_character_definition(self, definition: CharacterDefinition) -> None:
        """Insert a known definition without overwriting later team-maintained data."""

        async with self._session_factory() as database:
            existing = await database.get(CharacterDefinitionRecord, definition.npc_id)
            if existing is not None:
                return
            database.add(
                CharacterDefinitionRecord(
                    npc_id=definition.npc_id,
                    public_profile_json=definition.public_profile.model_dump(mode="json"),
                    private_profile_json=definition.private_profile,
                    sources_json=[source.model_dump(mode="json") for source in definition.sources],
                    setting_version=definition.setting_version,
                    completeness_status=definition.completeness_status,
                )
            )
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
                .order_by(MemoryRecord.occurred_turn, MemoryRecord.memory_id)
            )
            knowledge = list(knowledge_result.scalars())
            memories = list(memory_result.scalars())

        missing_data: list[str] = []
        if definition.completeness_status != "complete":
            missing_data.append("character_definition_incomplete")
        if not definition.private_profile_json:
            missing_data.append("private_character_profile_missing")
        if not definition.sources_json:
            missing_data.append("character_sources_missing")

        return NPCGenerationContext(
            npc_id=npc_id,
            setting_version=definition.setting_version,
            public_profile=definition.public_profile_json,
            private_profile=definition.private_profile_json,
            knowledge=[
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
            missing_data=missing_data,
        )
