from __future__ import annotations

"""
BackupService v1 (Phase 1).

This module is the hard-coded landing point for backup/restore workflows during
the refactor baseline work. The API will be filled in incrementally by the
corresponding Issue CSV tasks (create/restore/list).
"""

import logging
import json
from pathlib import Path
import re
import shutil
import sqlite3

from .backup_manager import BackupPaths, apply_retention_policy, format_backup_timestamp
from .backup_set import create_backup_set as create_backup_set_paths
from .backup_set import write_backup_manifest
from .sqlite_backup import backup_sqlite_db

logger = logging.getLogger(__name__)

_TIMESTAMP_DIR_RE = re.compile(r"^\d{8}-\d{6}$")


class BackupServiceError(RuntimeError):
    """Raised when a backup/restore operation fails."""


def _sqlite_integrity_check(db_path: Path) -> bool:
    try:
        with sqlite3.connect(str(db_path)) as conn:
            (result,) = conn.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.Error:
        return False

    return str(result).lower() == "ok"


def _copy_sqlite_db_files(source_db: Path, dest_db: Path) -> None:
    dest_db.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_db, dest_db)

    for suffix in ("-wal", "-shm"):
        source_aux = Path(f"{source_db}{suffix}")
        dest_aux = Path(f"{dest_db}{suffix}")

        if dest_aux.exists():
            dest_aux.unlink(missing_ok=True)
        if source_aux.exists():
            shutil.copy2(source_aux, dest_aux)


def create_backup_set(project_path: Path, db_paths: list[Path], reason: str) -> Path:
    """Create a backup set directory for the given databases and return the project backup dir."""
    timestamp = format_backup_timestamp()
    backup_set = create_backup_set_paths(project_path, timestamp=timestamp)

    project_db = None
    vectors_db = None

    for db_path in db_paths:
        if db_path.name == "project.db":
            dest_db = backup_set.project_db_path
            project_db = db_path
        elif db_path.name == "vectors.db":
            dest_db = backup_set.vectors_db_path
            vectors_db = db_path
        else:
            dest_db = backup_set.project_backup_dir / db_path.name

        logger.info("Backing up %s -> %s", db_path, dest_db)
        backup_sqlite_db(db_path, dest_db)

    write_backup_manifest(
        backup_set,
        project_dir=project_path,
        project_db=project_db,
        vectors_db=vectors_db,
        reason=reason,
    )

    apply_retention_policy(project_path / BackupPaths().project_backup_dir_name)
    apply_retention_policy(Path.home() / BackupPaths().global_app_dir_name / BackupPaths().global_backup_dir_name)

    return backup_set.project_backup_dir


def restore_backup_set(project_path: Path, backup_dir: Path) -> None:
    """Restore project.db (+ global vectors.db if present) from a backup set directory."""
    backup_dir = Path(backup_dir)
    project_path = Path(project_path)

    if not backup_dir.exists():
        raise BackupServiceError(f"Backup directory not found: {backup_dir}")

    timestamp = backup_dir.name
    backup_project_db = backup_dir / "project.db"
    if not backup_project_db.exists():
        raise BackupServiceError(f"Backup project.db not found: {backup_project_db}")

    if not _sqlite_integrity_check(backup_project_db):
        raise BackupServiceError(f"Backup project.db failed integrity_check: {backup_project_db}")

    backup_vectors_db = (
        Path.home()
        / BackupPaths().global_app_dir_name
        / BackupPaths().global_backup_dir_name
        / timestamp
        / "vectors.db"
    )
    if backup_vectors_db.exists() and not _sqlite_integrity_check(backup_vectors_db):
        raise BackupServiceError(f"Backup vectors.db failed integrity_check: {backup_vectors_db}")

    dest_project_db = project_path / "project.db"
    _copy_sqlite_db_files(backup_project_db, dest_project_db)

    if backup_vectors_db.exists():
        dest_vectors_db = (
            Path.home()
            / BackupPaths().global_app_dir_name
            / "vector_store"
            / "vectors.db"
        )
        _copy_sqlite_db_files(backup_vectors_db, dest_vectors_db)
    else:
        logger.warning("vectors.db not present in backup set; skipping vectors restore: %s", backup_vectors_db)


def list_backup_sets(project_path: Path) -> list[dict]:
    """List available backup sets for a project (for GUI display)."""
    project_path = Path(project_path)
    backup_root = project_path / BackupPaths().project_backup_dir_name
    if not backup_root.exists():
        return []

    backup_sets: list[dict] = []
    for path in backup_root.iterdir():
        if not path.is_dir() or not _TIMESTAMP_DIR_RE.match(path.name):
            continue

        timestamp = path.name
        backup_project_db = path / "project.db"
        manifest_path = path / "manifest.json"

        manifest: dict | None = None
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("Failed to read backup manifest: %s (%s)", manifest_path, exc)
                manifest = None

        backup_vectors_db = (
            Path.home()
            / BackupPaths().global_app_dir_name
            / BackupPaths().global_backup_dir_name
            / timestamp
            / "vectors.db"
        )

        backup_sets.append(
            {
                "timestamp": timestamp,
                "backup_dir": str(path),
                "project_db_path": str(backup_project_db),
                "project_db_exists": backup_project_db.exists(),
                "manifest_path": str(manifest_path),
                "manifest_exists": manifest_path.exists(),
                "vectors_db_path": str(backup_vectors_db),
                "vectors_db_exists": backup_vectors_db.exists(),
                "manifest": manifest,
            }
        )

    backup_sets.sort(key=lambda item: item["timestamp"], reverse=True)
    return backup_sets
