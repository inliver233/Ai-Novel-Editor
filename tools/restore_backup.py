from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core.backup_manager import BackupPaths
from core.backup_service import BackupServiceError, restore_backup_set


def _resolve_backup_dir(project_dir: Path, backup_arg: str) -> Path:
    backup_path = Path(backup_arg)
    if backup_path.exists():
        return backup_path
    if "/" in backup_arg or "\\" in backup_arg:
        return backup_path
    return project_dir / BackupPaths().project_backup_dir_name / backup_arg


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restore project backup set.")
    parser.add_argument("--project", required=True, help="Project directory path")
    parser.add_argument("--backup", required=True, help="Backup timestamp or directory path")
    args = parser.parse_args(argv)

    project_dir = Path(args.project)
    if not project_dir.exists():
        print(f"Project directory not found: {project_dir}", file=sys.stderr)
        return 2

    backup_dir = _resolve_backup_dir(project_dir, args.backup)
    try:
        restore_backup_set(project_dir, backup_dir)
    except BackupServiceError as exc:
        print(f"Restore failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Unexpected restore failure: {exc}", file=sys.stderr)
        return 1

    print(f"Restore completed: {backup_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
