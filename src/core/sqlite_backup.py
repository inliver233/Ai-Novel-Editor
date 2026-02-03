from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)


def backup_sqlite_db(source_db: str | Path, dest_db: str | Path) -> None:
    """Back up a SQLite database using the official backup API.

    This produces a consistent snapshot even when the source database is in WAL mode.
    """
    source_path = Path(source_db)
    dest_path = Path(dest_db)

    if not source_path.exists():
        raise FileNotFoundError(f"SQLite database not found: {source_path}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(str(source_path)) as src_conn, sqlite3.connect(
        str(dest_path)
    ) as dest_conn:
        src_conn.backup(dest_conn)
