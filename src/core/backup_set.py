from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .backup_manager import (
    format_backup_timestamp,
    get_global_vectors_backup_dir,
    get_project_backup_dir,
)
from .sqlite_backup import backup_sqlite_db


@dataclass(frozen=True)
class BackupSet:
    """A backup set groups related backup artifacts under the same timestamp."""

    timestamp: str
    project_backup_dir: Path
    project_db_path: Path
    manifest_path: Path
    vectors_backup_dir: Path
    vectors_db_path: Path


def create_backup_set(project_dir: str | Path, *, timestamp: str) -> BackupSet:
    project_backup_dir = get_project_backup_dir(project_dir, timestamp=timestamp)
    vectors_backup_dir = get_global_vectors_backup_dir(timestamp=timestamp)

    return BackupSet(
        timestamp=timestamp,
        project_backup_dir=project_backup_dir,
        project_db_path=project_backup_dir / "project.db",
        manifest_path=project_backup_dir / "manifest.json",
        vectors_backup_dir=vectors_backup_dir,
        vectors_db_path=vectors_backup_dir / "vectors.db",
    )


def create_backup_set_now(project_dir: str | Path) -> BackupSet:
    return create_backup_set(project_dir, timestamp=format_backup_timestamp())


def snapshot_project_db(backup_set: BackupSet, source_db: str | Path) -> Path:
    """Write a consistent project.db snapshot for this backup set."""
    backup_sqlite_db(source_db, backup_set.project_db_path)
    return backup_set.project_db_path
