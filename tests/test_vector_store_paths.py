from __future__ import annotations

from pathlib import Path

from core.vector_store_paths import ensure_project_vectors_db_path, get_project_vectors_db_path


def test_get_project_vectors_db_path() -> None:
    project_path = Path("C:/tmp/example_project")
    db_path = get_project_vectors_db_path(project_path)
    assert db_path.name == "vectors.db"
    assert db_path.parent.name == ".rag"
    assert db_path.parent.parent == project_path


def test_ensure_project_vectors_db_path_creates_dir(tmp_path: Path) -> None:
    project_path = tmp_path / "example_project"
    project_path.mkdir(parents=True, exist_ok=True)

    db_path = ensure_project_vectors_db_path(project_path)
    assert db_path.name == "vectors.db"
    assert db_path.parent.exists()
    assert db_path.parent.name == ".rag"
