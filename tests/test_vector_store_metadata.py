from __future__ import annotations

import tempfile
from pathlib import Path

from core.rag_service import RAGService, TextChunk
from core.sqlite_vector_store import SQLiteVectorStore


def test_vectors_db_records_store_metadata() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "vectors.db"
        store = SQLiteVectorStore(str(db_path))

        rag = RAGService(
            {
                "api_key": "",
                "embedding": {"model": "test-embed-model"},
                "rerank": {"enabled": False},
                "vector_store": {"chunk_size": 123, "chunk_overlap": 45, "chunker_version": "v1"},
            }
        )
        rag.set_vector_store(store)

        meta = store.get_store_metadata()
        assert meta["embedding_model"] == "test-embed-model"
        assert meta["chunk_size"] == 123
        assert meta["chunk_overlap"] == 45
        assert meta["chunker_version"] == "v1"

        chunks = [
            TextChunk(text="hello", chunk_index=0, document_id="doc", start_pos=0, end_pos=5)
        ]
        embeddings = [[0.1, 0.2, 0.3, 0.4]]
        store.store_embeddings(
            "doc",
            chunks,
            embeddings,
            "hello",
            embedding_model="test-embed-model",
            chunk_size=123,
            chunk_overlap=45,
            chunker_version="v1",
        )

        meta = store.get_store_metadata()
        assert meta["embedding_dim"] == 4

