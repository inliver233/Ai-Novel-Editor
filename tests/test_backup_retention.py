import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


def test_apply_retention_policy_keeps_newest_timestamp_dirs(tmp_path: Path) -> None:
    from core.backup_manager import apply_retention_policy

    root = tmp_path / "backups"
    root.mkdir()

    timestamps = [
        "20260203-000001",
        "20260203-000002",
        "20260203-000003",
    ]

    for ts in timestamps:
        (root / ts).mkdir()

    # Non-timestamp directories must not be affected.
    (root / "notes").mkdir()

    apply_retention_policy(root, keep_last=2)

    assert (root / "20260203-000003").exists()
    assert (root / "20260203-000002").exists()
    assert not (root / "20260203-000001").exists()
    assert (root / "notes").exists()
