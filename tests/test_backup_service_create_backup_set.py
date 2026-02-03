import json
import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_create_backup_set_backs_up_project_and_vectors(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from core.backup_service import create_backup_set

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
        conn.execute(
            "CREATE TABLE document_embeddings (id INTEGER PRIMARY KEY, embedding TEXT, embedding_model TEXT)"
        )
        conn.execute(
            "INSERT INTO document_embeddings (embedding, embedding_model) VALUES (?, ?)",
            (json.dumps([0.1, 0.2]), "db-model"),
        )
        conn.commit()

    backup_dir = create_backup_set(project_dir, [project_db, vectors_db], reason="import")

    assert backup_dir.exists()
    assert backup_dir.parent == project_dir / "backups"

    backup_project_db = backup_dir / "project.db"
    assert backup_project_db.exists()

    timestamp = backup_dir.name
    backup_vectors_db = tmp_path / ".ai-novel-editor" / "backups" / timestamp / "vectors.db"
    assert backup_vectors_db.exists()

    manifest_path = backup_dir / "manifest.json"
    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["reason"] == "import"
    assert manifest["project_db"]["schema_version"] == 2
    assert manifest["vectors"]["embedding_model"] == "db-model"
