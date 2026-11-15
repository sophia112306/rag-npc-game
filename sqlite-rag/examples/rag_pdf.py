"""Index PDF files into a SQLite database and retrieve passages for RAG.

Usage:
    python examples/rag_pdf.py index  paper.pdf            # one PDF or a folder
    python examples/rag_pdf.py search "What is the method?" # retrieve + build prompt

Requires the embedding model (download once):
    sqlite-rag download-model unsloth/embeddinggemma-300m-GGUF embeddinggemma-300M-Q8_0.gguf

sqlite-rag only does the retrieval half of RAG. The retrieved
sentences are sent to a local Ollama model (needs `ollama serve` running).
"""

import argparse
from pathlib import Path

import ollama
from sqlite_rag import SQLiteRag
from sqlite_rag.database import Database
from sqlite_rag.settings import SettingsManager

DB_PATH = "/mnt/d/AI小專案/code/story.db"
MODEL_PATH = "/mnt/d/AI小專案/code/sqlite-rag/models/unsloth/embeddinggemma-300m-GGUF/embeddinggemma-300M-Q8_0.gguf"
LLM_MODEL = "gemma4:12b"  # local Ollama model
TOP_SENTENCES = 6  # sentences kept per retrieved chunk and sent to the LLM


def open_rag() -> SQLiteRag:
    # The DB remembers the model path from the first run, and SQLiteRag.create()
    # rejects a different path as a "critical change". The file is the same
    # embedding model (same dim/type), so only the stored path is updated.
    conn = Database.new_connection(DB_PATH)
    settings = {"model_path": MODEL_PATH, "top_k_sentences": TOP_SENTENCES}
    SettingsManager(conn).configure(settings, force=True)
    conn.close()
    return SQLiteRag.create(DB_PATH, settings=settings)


def index_pdfs(path: str) -> None:
    rag = open_rag()
    # PDF -> text conversion is done by markitdown inside rag.add()
    processed = rag.add(path, recursive=True, only_extensions=["pdf"])
    print(f"Indexed {processed} new PDF(s) into {DB_PATH}")


def top_sentences_text(result, n: int = TOP_SENTENCES) -> str:
    """Top-n ranked sentences in document order, joined without gap markers."""
    top = sorted(
        result.sentences[:n],
        key=lambda s: s.start_offset if s.start_offset is not None else -1,
    )
    # fall back to the whole chunk when no sentences were extracted
    return " ".join(s.content for s in top) or result.chunk_content


def search(query: str, top_k: int = 2) -> None:
    rag = open_rag()
    results = rag.search(query, top_k=top_k)

    context_parts = []
    for i, r in enumerate(results[:top_k], 1):
        source = Path(r.document.uri or "unknown").name
        print(f"[{i}] {source}  (rank={r.combined_rank:.4f})")
        print(f"    {r.get_preview(top_k_sentences=TOP_SENTENCES, max_chars=1000)}\n")
        context_parts.append(f"[{i}] ({source})\n{top_sentences_text(r)}")

    context = "\n\n".join(context_parts)
    print("=" * 60)
    answer = ask_llm(query, context)
    print(f"Answer ({LLM_MODEL}):\n\n{answer}")


def ask_llm(query: str, context: str) -> str:
    response = ollama.chat(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "Answer the question using only the provided context. "
                    "Cite sources like [1]. If the context does not contain the "
                    "answer, say so. Reply in the language of the question."
                ),
            },
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"},
        ],
    )
    return response["message"]["content"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_index = sub.add_parser("index", help="index a PDF file or folder")
    p_index.add_argument("path")
    p_search = sub.add_parser("search", help="retrieve passages for a question")
    p_search.add_argument("query")
    p_search.add_argument("-k", type=int, default=5)
    args = parser.parse_args()

    if args.cmd == "index":
        index_pdfs(args.path)
    else:
        search(args.query, args.k)
