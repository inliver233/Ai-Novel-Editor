from __future__ import annotations

import logging
import shutil
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def copy_sqlite_db_files(source_db: str | Path, dest_db: str | Path) -> None:
    source_path = Path(source_db)
    dest_path = Path(dest_db)

    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {source_path}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_path, dest_path)

    for suffix in ("-wal", "-shm"):
        aux_source = Path(f"{source_path}{suffix}")
        if not aux_source.exists():
            continue
        aux_dest = Path(f"{dest_path}{suffix}")
        shutil.copy2(aux_source, aux_dest)


def backup_sqlite_db(source_db: str | Path, dest_db: str | Path) -> None:
    """Back up a SQLite database using the official backup API.

    This produces a consistent snapshot even when the source database is in WAL mode.
    """
    source_path = Path(source_db)
    dest_path = Path(dest_db)

    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {source_path}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    src_conn = sqlite3.connect(str(source_path))
    try:
        try:
            backup_fn = src_conn.backup
        except AttributeError:
            logger.warning("sqlite3.Connection.backup unavailable; falling back to file copy")
            copy_sqlite_db_files(source_path, dest_path)
            return

        dest_conn = sqlite3.connect(str(dest_path))
        try:
            backup_fn(dest_conn)
        finally:
            dest_conn.close()
    finally:
        src_conn.close()
