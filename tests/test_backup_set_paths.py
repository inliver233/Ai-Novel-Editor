import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_create_backup_set_paths() -> None:
    from core.backup_set import create_backup_set

    project_dir = Path("C:/example/project")
    timestamp = "20260203-010203"

    backup_set = create_backup_set(project_dir, timestamp=timestamp)

    assert backup_set.project_backup_dir == project_dir / "backups" / timestamp
    assert backup_set.project_db_path == project_dir / "backups" / timestamp / "project.db"
    assert backup_set.manifest_path == project_dir / "backups" / timestamp / "manifest.json"

    assert backup_set.vectors_backup_dir == (
        Path.home() / ".ai-novel-editor" / "backups" / timestamp
    )
    assert backup_set.vectors_db_path == (
        Path.home() / ".ai-novel-editor" / "backups" / timestamp / "vectors.db"
    )
