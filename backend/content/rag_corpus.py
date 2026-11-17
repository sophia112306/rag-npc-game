"""Load the reviewed, retrieval-ready NPC knowledge corpus."""

from functools import lru_cache
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas.content import KnowledgeItem


CORPUS_PATH = Path(__file__).resolve().parents[2] / "rag" / "corpus" / "npc_knowledge.jsonl"


class RAGCorpusEntry(BaseModel):
    """One source-traceable chunk that may be embedded without changing metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    chunk_id: str = Field(..., min_length=1, max_length=120)
    text: str = Field(..., min_length=1)
    npc_ids: tuple[str, ...] = Field(..., min_length=1)
    session_id: str | None = None
    visibility: Literal["public", "conditional", "private", "secret"]
    knowledge_type: str = Field(..., min_length=1, max_length=50)
    unlock_condition: str = Field(..., min_length=1, max_length=100)
    available_from_turn: int = Field(..., ge=0)
    canon_version: int = Field(..., ge=1)
    source_id: str = Field(..., min_length=1, max_length=100)
    source_locator: str = Field(..., min_length=1, max_length=500)
    epistemic_status: Literal["confirmed", "provisional", "hearsay"]
    keywords: tuple[str, ...] = ()

    def as_knowledge_item(self) -> KnowledgeItem:
        return KnowledgeItem(
            knowledge_id=self.chunk_id,
            subject_key=self.chunk_id.rsplit(".v", 1)[0],
            content=self.text,
            epistemic_status=self.epistemic_status,
            source_kind="reviewed_rag_corpus",
            source_id=self.source_id,
            acquired_turn=0,
            provenance={
                "source_locator": self.source_locator,
                "visibility": self.visibility,
                "knowledge_type": self.knowledge_type,
                "unlock_condition": self.unlock_condition,
                "canon_version": self.canon_version,
                "keywords": list(self.keywords),
            },
        )


@lru_cache(maxsize=1)
def load_rag_corpus() -> tuple[RAGCorpusEntry, ...]:
    """Validate every JSONL row at startup or first authorized retrieval."""

    entries: list[RAGCorpusEntry] = []
    seen_ids: set[str] = set()
    with CORPUS_PATH.open(encoding="utf-8") as corpus_file:
        for line_number, raw_line in enumerate(corpus_file, 1):
            line = raw_line.strip()
            if not line:
                continue
            entry = RAGCorpusEntry.model_validate(json.loads(line))
            if entry.chunk_id in seen_ids:
                raise ValueError(
                    f"Duplicate RAG chunk_id '{entry.chunk_id}' on line {line_number}"
                )
            seen_ids.add(entry.chunk_id)
            entries.append(entry)
    return tuple(entries)


def public_knowledge_for_npc(
    npc_id: str,
    *,
    current_turn: int,
    setting_version: int,
) -> list[KnowledgeItem]:
    """Return only global public chunks authorized for this NPC and turn."""

    return [
        entry.as_knowledge_item()
        for entry in load_rag_corpus()
        if entry.session_id is None
        and entry.visibility == "public"
        and entry.unlock_condition == "always"
        and npc_id in entry.npc_ids
        and entry.available_from_turn <= current_turn
        and entry.canon_version == setting_version
    ]
