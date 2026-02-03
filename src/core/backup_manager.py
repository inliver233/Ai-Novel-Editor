from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class BackupPaths:
    """Default backup paths (hard-coded)."""

    project_backup_dir_name: str = "backups"
    timestamp_format: str = "%Y%m%d-%H%M%S"
    global_app_dir_name: str = ".ai-novel-editor"
    global_backup_dir_name: str = "backups"


def format_backup_timestamp(dt: datetime | None = None) -> str:
    """Format timestamp for backup directory names: YYYYMMDD-HHMMSS."""
    dt = dt or datetime.now()
    return dt.strftime(BackupPaths().timestamp_format)


def get_project_backup_dir(project_dir: str | Path, *, timestamp: str) -> Path:
    project_path = Path(project_dir)
    return project_path / BackupPaths().project_backup_dir_name / timestamp


def get_project_db_backup_path(project_dir: str | Path, *, timestamp: str) -> Path:
    return get_project_backup_dir(project_dir, timestamp=timestamp) / "project.db"


def get_global_vectors_backup_dir(*, timestamp: str) -> Path:
    base_dir = Path.home() / BackupPaths().global_app_dir_name / BackupPaths().global_backup_dir_name
    return base_dir / timestamp


def get_global_vectors_db_backup_path(*, timestamp: str) -> Path:
    return get_global_vectors_backup_dir(timestamp=timestamp) / "vectors.db"
