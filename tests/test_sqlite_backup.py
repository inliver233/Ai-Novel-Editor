import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_backup_sqlite_db_creates_consistent_snapshot(tmp_path: Path) -> None:
    from core.sqlite_backup import backup_sqlite_db

    source_db = tmp_path / "project.db"
    backup_db = tmp_path / "backup.db"

    with sqlite3.connect(source_db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT NOT NULL)")
        conn.execute("INSERT INTO t (v) VALUES ('hello')")
        conn.commit()

    backup_sqlite_db(source_db, backup_db)

    assert backup_db.exists()

    with sqlite3.connect(backup_db) as conn:
        (value,) = conn.execute("SELECT v FROM t WHERE id = 1").fetchone()
        assert value == "hello"
