import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_restore_backup_set_restores_project_and_vectors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from core.backup_service import create_backup_set, restore_backup_set

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    project_db = project_dir / "project.db"
    with sqlite3.connect(project_db) as conn:
        conn.execute("CREATE TABLE project_metadata (id INTEGER PRIMARY KEY, version TEXT)")
        conn.execute("INSERT INTO project_metadata (version) VALUES ('schema_v2')")
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT NOT NULL)")
        conn.execute("INSERT INTO t (v) VALUES ('v1')")
        conn.commit()

    vectors_db = tmp_path / ".ai-novel-editor" / "vector_store" / "vectors.db"
    vectors_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(vectors_db) as conn:
        conn.execute("CREATE TABLE document_embeddings (id INTEGER PRIMARY KEY, embedding TEXT)")
        conn.execute("INSERT INTO document_embeddings (embedding) VALUES ('v1')")
        conn.commit()

    backup_dir = create_backup_set(project_dir, [project_db, vectors_db], reason="test")

    with sqlite3.connect(project_db) as conn:
        conn.execute("UPDATE t SET v = 'v2' WHERE id = 1")
        conn.commit()
    with sqlite3.connect(vectors_db) as conn:
        conn.execute("UPDATE document_embeddings SET embedding = 'v2' WHERE id = 1")
        conn.commit()

    restore_backup_set(project_dir, backup_dir)

    with sqlite3.connect(project_db) as conn:
        (value,) = conn.execute("SELECT v FROM t WHERE id = 1").fetchone()
        assert value == "v1"
    with sqlite3.connect(vectors_db) as conn:
        (value,) = conn.execute("SELECT embedding FROM document_embeddings WHERE id = 1").fetchone()
        assert value == "v1"
