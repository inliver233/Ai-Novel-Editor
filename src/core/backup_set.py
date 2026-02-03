from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any

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


def snapshot_vectors_db(backup_set: BackupSet, source_db: str | Path) -> Path:
    """Write a consistent vectors.db snapshot for this backup set."""
    backup_sqlite_db(source_db, backup_set.vectors_db_path)
    return backup_set.vectors_db_path


_SCHEMA_VERSION_RE = re.compile(r"^schema_v(\d+)$")


def _read_project_db_schema_version(project_db: str | Path) -> int | None:
    db_path = Path(project_db)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute("SELECT version FROM project_metadata LIMIT 1").fetchone()
    except sqlite3.Error:
        return None

    if not row or not row[0]:
        return None

    value = str(row[0])
    match = _SCHEMA_VERSION_RE.match(value)
    if match:
        return int(match.group(1))

    try:
        return int(value)
    except ValueError:
        return None


def _infer_vectors_embedding_model(vectors_db: str | Path) -> str | None:
    db_path = Path(vectors_db)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT embedding_model FROM document_embeddings "
                "WHERE embedding_model IS NOT NULL AND embedding_model != '' "
                "LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return None

    if not row or not row[0]:
        return None

    return str(row[0])


def _infer_vectors_embedding_dim(vectors_db: str | Path) -> int | None:
    db_path = Path(vectors_db)
    if not db_path.exists():
        return None

    try:
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT embedding FROM document_embeddings LIMIT 1"
            ).fetchone()
    except sqlite3.Error:
        return None

    if not row or row[0] is None:
        return None

    data = row[0]
    if isinstance(data, bytes):
        try:
            data = data.decode("utf-8")
        except UnicodeDecodeError:
            return None

    try:
        embedding = json.loads(data)
    except json.JSONDecodeError:
        return None

    if not isinstance(embedding, list):
        return None

    return len(embedding)


_APP_VERSION_RE = re.compile(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]\s*$")


def _read_app_version_from_src_init() -> str | None:
    src_dir = Path(__file__).resolve().parents[1]
    init_path = src_dir / "__init__.py"
    if not init_path.exists():
        return None

    try:
        for line in init_path.read_text(encoding="utf-8").splitlines():
            match = _APP_VERSION_RE.match(line.strip())
            if match:
                return match.group(1)
    except OSError:
        return None

    return None


def _sanitize_project_path(project_dir: str | Path) -> str:
    project_path = Path(project_dir)
    try:
        resolved = project_path.resolve()
    except OSError:
        resolved = project_path

    name = project_path.name or resolved.name or "project"
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:12]
    return f"{name}#{digest}"


def write_backup_manifest(
    backup_set: BackupSet,
    *,
    project_dir: str | Path,
    project_db: str | Path | None = None,
    vectors_db: str | Path | None = None,
    rag_config: dict[str, Any] | None = None,
    app_version: str | None = None,
) -> Path:
    """Write backup set manifest.json.

    This manifest is designed to be safe to share: it stores a sanitized project
    path rather than an absolute local filesystem path.
    """
    app_version = app_version or _read_app_version_from_src_init() or "unknown"
    schema_version = _read_project_db_schema_version(project_db or backup_set.project_db_path) or 1

    embedding_model = None
    embedding_dim = None
    if vectors_db is not None:
        embedding_model = _infer_vectors_embedding_model(vectors_db)
        embedding_dim = _infer_vectors_embedding_dim(vectors_db)

    chunk_size = None
    chunk_overlap = None
    if rag_config:
        embedding_model = embedding_model or rag_config.get("embedding", {}).get("model")
        vector_store = rag_config.get("vector_store", {})
        chunk_size = vector_store.get("chunk_size")
        chunk_overlap = vector_store.get("chunk_overlap")

    manifest: dict[str, Any] = {
        "timestamp": backup_set.timestamp,
        "app_version": str(app_version),
        "project_path": _sanitize_project_path(project_dir),
        "project_db": {"schema_version": schema_version},
        "vectors": {
            "embedding_model": embedding_model,
            "embedding_dim": embedding_dim,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        },
    }

    backup_set.manifest_path.parent.mkdir(parents=True, exist_ok=True)
    backup_set.manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return backup_set.manifest_path
