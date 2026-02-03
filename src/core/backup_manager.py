from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re
import shutil


@dataclass(frozen=True)
class BackupPaths:
    """Default backup paths (hard-coded)."""

    project_backup_dir_name: str = "backups"
    timestamp_format: str = "%Y%m%d-%H%M%S"
    global_app_dir_name: str = ".ai-novel-editor"
    global_backup_dir_name: str = "backups"


DEFAULT_RETENTION_COUNT = 10


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


_TIMESTAMP_DIR_RE = re.compile(r"^\d{8}-\d{6}$")


def apply_retention_policy(backup_root: str | Path, *, keep_last: int = DEFAULT_RETENTION_COUNT) -> None:
    """Keep only the newest N timestamped backup directories."""
    if keep_last < 1:
        raise ValueError("keep_last must be >= 1")

    root = Path(backup_root)
    if not root.exists():
        return

    candidates = [
        path
        for path in root.iterdir()
        if path.is_dir() and _TIMESTAMP_DIR_RE.match(path.name)
    ]
    candidates.sort(key=lambda p: p.name, reverse=True)

    for path in candidates[keep_last:]:
        shutil.rmtree(path, ignore_errors=True)
