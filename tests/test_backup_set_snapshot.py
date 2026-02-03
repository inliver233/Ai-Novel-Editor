import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_snapshot_project_db_writes_backup_set_file(tmp_path: Path) -> None:
    from core.backup_set import create_backup_set, snapshot_project_db

    project_dir = tmp_path
    source_db = project_dir / "project.db"

    with sqlite3.connect(source_db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT NOT NULL)")
        conn.execute("INSERT INTO t (v) VALUES ('hello')")
        conn.commit()

    backup_set = create_backup_set(project_dir, timestamp="20260203-010203")
    snapshot_project_db(backup_set, source_db)

    assert backup_set.project_db_path.exists()

    with sqlite3.connect(backup_set.project_db_path) as conn:
        (value,) = conn.execute("SELECT v FROM t WHERE id = 1").fetchone()
        assert value == "hello"


def test_snapshot_vectors_db_writes_backup_set_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from core.backup_set import create_backup_set, snapshot_vectors_db

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    source_db = tmp_path / "vectors_source.db"

    with sqlite3.connect(source_db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE embeddings (id INTEGER PRIMARY KEY, v TEXT NOT NULL)")
        conn.execute("INSERT INTO embeddings (v) VALUES ('vec')")
        conn.commit()

    backup_set = create_backup_set(project_dir, timestamp="20260203-010203")
    snapshot_vectors_db(backup_set, source_db)

    assert backup_set.vectors_db_path.exists()

    with sqlite3.connect(backup_set.vectors_db_path) as conn:
        (value,) = conn.execute("SELECT v FROM embeddings WHERE id = 1").fetchone()
        assert value == "vec"
