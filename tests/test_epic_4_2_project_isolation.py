from __future__ import annotations

from pathlib import Path

from core.sqlite_vector_store import SQLiteVectorStore


def test_project_id_filtering_isolates_projects_in_one_db(tmp_path: Path) -> None:
    db_path = tmp_path / "vectors.db"

    store_a = SQLiteVectorStore(str(db_path), project_id="project-A")
    store_b = SQLiteVectorStore(str(db_path), project_id="project-B")

    store_a.store_embedding(
        document_id="doc_a",
        chunk_index=0,
        chunk_text="alpha only content",
        start_pos=0,
        end_pos=5,
        embedding=[0.1],
        embedding_model="test-embed",
        metadata=None,
    )
    store_b.store_embedding(
        document_id="doc_b",
        chunk_index=0,
        chunk_text="beta only content",
        start_pos=0,
        end_pos=4,
        embedding=[0.2],
        embedding_model="test-embed",
        metadata=None,
    )

    a_alpha = store_a.similarity_search_ultra_fast("alpha", limit=10)
    b_alpha = store_b.similarity_search_ultra_fast("alpha", limit=10)
    a_beta = store_a.similarity_search_ultra_fast("beta", limit=10)
    b_beta = store_b.similarity_search_ultra_fast("beta", limit=10)

    assert [row["document_id"] for row in a_alpha] == ["doc_a"]
    assert b_alpha == []
    assert a_beta == []
    assert [row["document_id"] for row in b_beta] == ["doc_b"]

    assert [row["document_id"] for row in store_a.get_all_embeddings()] == ["doc_a"]
    assert [row["document_id"] for row in store_b.get_all_embeddings()] == ["doc_b"]

    deleted = store_a.delete_document_embeddings("doc_a")
    assert deleted == 1
    assert store_a.document_exists("doc_a") is False
    assert store_b.document_exists("doc_b") is True

