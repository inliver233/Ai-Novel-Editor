import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_list_backup_sets_empty_when_no_backups(tmp_path: Path) -> None:
    from core.backup_service import list_backup_sets

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    assert list_backup_sets(project_dir) == []


def test_list_backup_sets_returns_sorted_items_with_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from core import backup_service
    from core.backup_service import create_backup_set, list_backup_sets

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    project_db = project_dir / "project.db"
    with sqlite3.connect(project_db) as conn:
        conn.execute("CREATE TABLE project_metadata (id INTEGER PRIMARY KEY, version TEXT)")
        conn.execute("INSERT INTO project_metadata (version) VALUES ('schema_v2')")
        conn.commit()

    vectors_db = tmp_path / ".ai-novel-editor" / "vector_store" / "vectors.db"
    vectors_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(vectors_db) as conn:
        conn.execute("CREATE TABLE document_embeddings (id INTEGER PRIMARY KEY, embedding TEXT)")
        conn.execute("INSERT INTO document_embeddings (embedding) VALUES ('v1')")
        conn.commit()

    monkeypatch.setattr(backup_service, "format_backup_timestamp", lambda dt=None: "20260203-010203")
    create_backup_set(project_dir, [project_db, vectors_db], reason="first")

    monkeypatch.setattr(backup_service, "format_backup_timestamp", lambda dt=None: "20260203-010204")
    create_backup_set(project_dir, [project_db, vectors_db], reason="second")

    (project_dir / "backups" / "not-a-timestamp").mkdir(parents=True)

    backups = list_backup_sets(project_dir)

    assert [item["timestamp"] for item in backups] == ["20260203-010204", "20260203-010203"]
    assert backups[0]["project_db_exists"] is True
    assert backups[0]["vectors_db_exists"] is True
    assert backups[0]["manifest_exists"] is True
    assert backups[0]["manifest"]["reason"] == "second"

