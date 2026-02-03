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
