from __future__ import annotations

import os
from pathlib import Path


def get_legacy_global_vectors_db_path() -> Path:
    """Legacy global vectors.db location (pre per-project isolation)."""
    return Path(os.path.expanduser("~/.ai-novel-editor/vector_store/vectors.db"))


def get_project_vectors_db_path(project_path: Path) -> Path:
    """Per-project vectors.db location: <project_path>/.rag/vectors.db."""
    return project_path / ".rag" / "vectors.db"


def ensure_project_vectors_db_path(project_path: Path) -> Path:
    """Ensure the per-project vectors.db parent directory exists and return the path."""
    db_path = get_project_vectors_db_path(project_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return db_path
