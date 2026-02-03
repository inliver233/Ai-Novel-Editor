import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_clear_all_creates_backup_before_deleting(tmp_path: Path, monkeypatch) -> None:
    import core.backup_workflows as workflows
    from core.sqlite_vector_store import SQLiteVectorStore

    db_path = tmp_path / "vectors.db"
    store = SQLiteVectorStore(str(db_path))

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO document_embeddings (document_id, chunk_index, chunk_text, start_pos, end_pos, embedding) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("doc", 0, "text", 0, 4, "[1,2,3]"),
        )
        conn.commit()

        (count_before,) = conn.execute("SELECT COUNT(*) FROM document_embeddings").fetchone()
        assert count_before == 1

    called = {"ok": False}

    def _fake_backup(vectors_db, **_kwargs):
        with sqlite3.connect(vectors_db) as conn:
            (count_at_backup,) = conn.execute(
                "SELECT COUNT(*) FROM document_embeddings"
            ).fetchone()
            assert count_at_backup == 1
        called["ok"] = True

    monkeypatch.setattr(workflows, "create_pre_vectors_clear_backup", _fake_backup)

    store.clear_all()

    assert called["ok"] is True

    with sqlite3.connect(db_path) as conn:
        (count_after,) = conn.execute("SELECT COUNT(*) FROM document_embeddings").fetchone()
        assert count_after == 0
