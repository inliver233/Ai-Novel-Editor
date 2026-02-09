from __future__ import annotations

from pathlib import Path

from core.import_manager import ImportFormat, ImportManager, ImportOptions


class _DummyProjectManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def create_project(self, name: str, path: str, *args, **kwargs) -> bool:  # noqa: D401
        self.calls.append((name, path))
        return True


def test_create_project_uses_selected_path(tmp_path: Path) -> None:
    input_path = tmp_path / "book.md"
    input_path.write_text("# title\n", encoding="utf-8")

    project_parent = tmp_path / "projects"
    project_parent.mkdir()

    pm = _DummyProjectManager()
    manager = ImportManager(pm)
    options = ImportOptions(
        format=ImportFormat.MARKDOWN,
        input_path=input_path,
        create_project=True,
        project_name="MyBook",
        project_path=project_parent / "MyBook",
    )

    assert manager._create_project_if_requested(options) is True
    assert pm.calls == [("MyBook", str(project_parent / "MyBook"))]


def test_create_project_rejects_non_empty_target_dir(tmp_path: Path) -> None:
    input_path = tmp_path / "book.txt"
    input_path.write_text("hello", encoding="utf-8")

    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "existing.txt").write_text("data", encoding="utf-8")

    pm = _DummyProjectManager()
    manager = ImportManager(pm)
    options = ImportOptions(
        format=ImportFormat.TEXT,
        input_path=input_path,
        create_project=True,
        project_name="Target",
        project_path=target_dir,
    )

    assert manager._create_project_if_requested(options) is False
    assert pm.calls == []

