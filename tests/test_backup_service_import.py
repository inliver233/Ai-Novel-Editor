import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_backup_service_module_importable() -> None:
    from core.backup_service import BackupServiceError

    assert issubclass(BackupServiceError, RuntimeError)
