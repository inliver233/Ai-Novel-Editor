from __future__ import annotations

"""
BackupService v1 (Phase 1).

This module is the hard-coded landing point for backup/restore workflows during
the refactor baseline work. The API will be filled in incrementally by the
corresponding Issue CSV tasks (create/restore/list).
"""

import logging
from pathlib import Path

from .backup_manager import BackupPaths, apply_retention_policy, format_backup_timestamp
from .backup_set import create_backup_set as create_backup_set_paths
from .backup_set import write_backup_manifest
from .sqlite_backup import backup_sqlite_db

logger = logging.getLogger(__name__)


class BackupServiceError(RuntimeError):
    """Raised when a backup/restore operation fails."""


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
