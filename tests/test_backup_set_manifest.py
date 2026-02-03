import json
import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_write_backup_manifest_includes_required_metadata(tmp_path: Path) -> None:
    from core.backup_set import create_backup_set, write_backup_manifest

    project_dir = tmp_path / "my_project"
    project_dir.mkdir()

    project_db = project_dir / "project.db"
    with sqlite3.connect(project_db) as conn:
        conn.execute("CREATE TABLE project_metadata (id INTEGER PRIMARY KEY, version TEXT)")
        conn.execute("INSERT INTO project_metadata (version) VALUES ('schema_v2')")
        conn.commit()

    vectors_db = tmp_path / "vectors.db"
    with sqlite3.connect(vectors_db) as conn:
        conn.execute(
            "CREATE TABLE document_embeddings (id INTEGER PRIMARY KEY, embedding TEXT, embedding_model TEXT)"
        )
        conn.execute(
            "INSERT INTO document_embeddings (embedding, embedding_model) VALUES (?, ?)",
            (json.dumps([0.1, 0.2, 0.3]), "db-model"),
        )
        conn.commit()

    rag_config = {
        "embedding": {"model": "cfg-model"},
        "vector_store": {"chunk_size": 250, "chunk_overlap": 50},
    }

    backup_set = create_backup_set(project_dir, timestamp="20260203-010203")
    manifest_path = write_backup_manifest(
        backup_set,
        project_dir=project_dir,
        project_db=project_db,
        vectors_db=vectors_db,
        rag_config=rag_config,
        app_version="9.9.9",
    )

    assert manifest_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["timestamp"] == "20260203-010203"
    assert manifest["app_version"] == "9.9.9"
    assert manifest["project_db"]["schema_version"] == 2

    project_path = manifest["project_path"]
    assert project_dir.name in project_path
    assert str(project_dir) not in project_path

    assert manifest["vectors"]["embedding_model"] == "db-model"
    assert manifest["vectors"]["embedding_dim"] == 3
    assert manifest["vectors"]["chunk_size"] == 250
    assert manifest["vectors"]["chunk_overlap"] == 50
