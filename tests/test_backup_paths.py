import sys
from datetime import datetime
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_project_db_backup_path() -> None:
    from core.backup_manager import get_project_db_backup_path

    project_dir = Path("C:/example/project")
    timestamp = "20260203-010203"

    assert get_project_db_backup_path(project_dir, timestamp=timestamp) == (
        project_dir / "backups" / timestamp / "project.db"
    )


def test_format_backup_timestamp() -> None:
    from core.backup_manager import format_backup_timestamp

    assert format_backup_timestamp(datetime(2026, 2, 3, 1, 2, 3)) == "20260203-010203"


def test_global_vectors_db_backup_path() -> None:
    from core.backup_manager import get_global_vectors_db_backup_path

    timestamp = "20260203-010203"
    assert get_global_vectors_db_backup_path(timestamp=timestamp) == (
        Path.home() / ".ai-novel-editor" / "backups" / timestamp / "vectors.db"
    )
