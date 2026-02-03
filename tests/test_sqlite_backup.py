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


def test_backup_sqlite_db_supports_vectors_db_path(tmp_path: Path) -> None:
    from core.sqlite_backup import backup_sqlite_db

    source_db = tmp_path / "vectors.db"
    backup_db = tmp_path / "vectors.backup.db"

    with sqlite3.connect(source_db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE embeddings (id INTEGER PRIMARY KEY, v TEXT NOT NULL)")
        conn.execute("INSERT INTO embeddings (v) VALUES ('vec')")
        conn.commit()

    backup_sqlite_db(source_db, backup_db)

    with sqlite3.connect(backup_db) as conn:
        (value,) = conn.execute("SELECT v FROM embeddings WHERE id = 1").fetchone()
        assert value == "vec"


def test_copy_sqlite_db_files_copies_wal_and_shm_when_present(tmp_path: Path) -> None:
    from core.sqlite_backup import copy_sqlite_db_files

    source_db = tmp_path / "data.db"
    backup_db = tmp_path / "data.backup.db"

    with sqlite3.connect(source_db) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, v TEXT NOT NULL)")
        conn.execute("INSERT INTO t (v) VALUES ('x')")
        conn.commit()

    # Ensure auxiliary WAL/SHM files exist so the test is deterministic.
    wal_path = Path(f"{source_db}-wal")
    shm_path = Path(f"{source_db}-shm")
    if not wal_path.exists():
        wal_path.write_bytes(b"wal")
    if not shm_path.exists():
        shm_path.write_bytes(b"shm")

    copy_sqlite_db_files(source_db, backup_db)

    assert backup_db.exists()
    assert Path(f"{backup_db}-wal").exists()
    assert Path(f"{backup_db}-shm").exists()
