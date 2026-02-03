import json
import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_create_pre_import_backup_creates_backup_set(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    from core.backup_workflows import create_pre_import_backup, get_global_vectors_db_path

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    project_db = project_dir / "project.db"
    with sqlite3.connect(project_db) as conn:
        conn.execute("CREATE TABLE project_metadata (id INTEGER PRIMARY KEY, version TEXT)")
        conn.execute("INSERT INTO project_metadata (version) VALUES ('schema_v2')")
        conn.commit()

    vectors_db = get_global_vectors_db_path()
    vectors_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(vectors_db) as conn:
        conn.execute(
            "CREATE TABLE document_embeddings (id INTEGER PRIMARY KEY, embedding TEXT, embedding_model TEXT)"
        )
        conn.execute(
            "INSERT INTO document_embeddings (embedding, embedding_model) VALUES (?, ?)",
            (json.dumps([1, 2, 3, 4]), "db-model"),
        )
        conn.commit()

    rag_config = {"vector_store": {"chunk_size": 250, "chunk_overlap": 50}}

    backup_set = create_pre_import_backup(project_dir, rag_config=rag_config)

    assert backup_set.project_backup_dir.parent == project_dir / "backups"
    assert backup_set.project_db_path.exists()
    assert backup_set.manifest_path.exists()
    assert backup_set.vectors_db_path.exists()

    manifest = json.loads(backup_set.manifest_path.read_text(encoding="utf-8"))
    assert manifest["project_db"]["schema_version"] == 2
    assert manifest["vectors"]["embedding_model"] == "db-model"
    assert manifest["vectors"]["embedding_dim"] == 4
