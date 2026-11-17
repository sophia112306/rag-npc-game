"""Validation and authorization tests for the reviewed starter RAG corpus."""

from backend.content.rag_corpus import load_rag_corpus, public_knowledge_for_npc


def test_rag_corpus_has_unique_traceable_chunks_for_the_two_trained_npcs() -> None:
    entries = load_rag_corpus()

    assert len(entries) == 6
    assert len({entry.chunk_id for entry in entries}) == len(entries)
    assert {npc_id for entry in entries for npc_id in entry.npc_ids} == {
        "vidalia",
        "menmesvento",
    }
    assert all(entry.source_id and entry.source_locator for entry in entries)
    assert all(entry.visibility == "public" for entry in entries)
    assert all(entry.canon_version == 2 for entry in entries)


def test_public_rag_retrieval_never_crosses_npc_or_version_boundary() -> None:
    vidalia = public_knowledge_for_npc(
        "vidalia", current_turn=0, setting_version=2
    )
    menmesvento = public_knowledge_for_npc(
        "menmesvento", current_turn=0, setting_version=2
    )

    assert {item.subject_key for item in vidalia} == {
        "vidalia.profile",
        "vidalia.life_spring",
        "vidalia.investigation",
    }
    assert {item.subject_key for item in menmesvento} == {
        "menmesvento.profile",
        "menmesvento.names",
        "menmesvento.scroll",
    }
    assert public_knowledge_for_npc(
        "vidalia", current_turn=0, setting_version=1
    ) == []
    assert all(item.source_kind == "reviewed_rag_corpus" for item in vidalia)
