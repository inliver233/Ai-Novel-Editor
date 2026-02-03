import sqlite3
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def _table_columns(db_path: Path, table: str) -> set[str]:
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def test_migrate_database_creates_pre_migration_backup(tmp_path: Path) -> None:
    from core.database_manager import DatabaseManager

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    manager = DatabaseManager(str(project_dir))

    backups_root = project_dir / "backups"
    assert backups_root.exists()

    backup_dirs = [p for p in backups_root.iterdir() if p.is_dir()]
    assert len(backup_dirs) == 1

    backup_db = backup_dirs[0] / "project.db"
    assert backup_db.exists()

    # Backup is taken BEFORE migration alters `codex_references`.
    assert "updated_at" not in _table_columns(backup_db, "codex_references")

    # Current DB should be migrated to include the new columns.
    assert "updated_at" in _table_columns(manager.db_path, "codex_references")
