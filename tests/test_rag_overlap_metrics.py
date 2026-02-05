from __future__ import annotations

import json
from pathlib import Path

from core.rag_service import RAGService
from tests.fixtures.fake_embedder import FakeEmbedder


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"


def _load_queries() -> list[str]:
    queries = (FIXTURES_DIR / "rag_queries.txt").read_text(encoding="utf-8").splitlines()
    return [q.strip() for q in queries if q.strip()]


def _load_corpus() -> str:
    return (FIXTURES_DIR / "rag_corpus.txt").read_text(encoding="utf-8")


def _chunk_id(chunk) -> str:
    return f"{chunk.document_id}:{chunk.chunk_index}"


def test_rag_overlap_metrics() -> None:
    queries = _load_queries()
    corpus = _load_corpus()

    embedder = FakeEmbedder(dims=16)
    rag = RAGService({"rerank": {"enabled": False}}, embedder=embedder)

    chunks = rag.chunk_text(corpus, document_id="rag_corpus", chunk_size=80, chunk_overlap=20)
    chunk_embeddings = embedder.embed_batch([chunk.text for chunk in chunks])

    baseline_path = GOLDEN_DIR / "rag_overlap.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    top_n = int(baseline["top_n"])

    baseline_queries = [entry["query"] for entry in baseline["queries"]]
    assert baseline_queries == queries

    overlaps = []
    for entry in baseline["queries"]:
        expected_ids = set(entry["result_ids"])
        results = rag.search(
            entry["query"],
            chunks,
            chunk_embeddings,
            max_results=top_n,
            min_similarity=0.0,
        )
        actual_ids = {_chunk_id(result.chunk) for result in results[:top_n]}
        overlap = len(actual_ids & expected_ids) / len(expected_ids) if expected_ids else 1.0
        overlaps.append(overlap)

    average_overlap = sum(overlaps) / len(overlaps)
    assert average_overlap >= 0.8
