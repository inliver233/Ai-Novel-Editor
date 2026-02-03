from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .backup_manager import BackupPaths, apply_retention_policy
from .backup_set import (
    BackupSet,
    create_backup_set_now,
    snapshot_project_db,
    snapshot_vectors_db,
    write_backup_manifest,
)

logger = logging.getLogger(__name__)


def get_global_vectors_db_path() -> Path:
    """Return the default global vectors.db path (hard-coded)."""
    return Path.home() / ".ai-novel-editor" / "vector_store" / "vectors.db"


def create_pre_import_backup(
    project_dir: str | Path,
    *,
    project_db: str | Path | None = None,
    vectors_db: str | Path | None = None,
    rag_config: dict[str, Any] | None = None,
) -> BackupSet:
    """Create a backup set before a potentially destructive import."""
    project_path = Path(project_dir)
    project_db_path = Path(project_db) if project_db is not None else project_path / "project.db"

    backup_set = create_backup_set_now(project_path)
    snapshot_project_db(backup_set, project_db_path)

    vectors_db_path = Path(vectors_db) if vectors_db is not None else get_global_vectors_db_path()
    if vectors_db_path.exists():
        snapshot_vectors_db(backup_set, vectors_db_path)
    else:
        logger.warning("Vectors DB not found; skipping vectors snapshot: %s", vectors_db_path)
        vectors_db_path = None

    write_backup_manifest(
        backup_set,
        project_dir=project_path,
        project_db=project_db_path,
        vectors_db=vectors_db_path,
        rag_config=rag_config,
    )

    apply_retention_policy(project_path / BackupPaths().project_backup_dir_name)
    apply_retention_policy(Path.home() / BackupPaths().global_app_dir_name / BackupPaths().global_backup_dir_name)

    return backup_set
