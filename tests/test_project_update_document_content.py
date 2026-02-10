from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from core.config import Config
from core.project import ProjectManager
from core.shared import Shared
from gui.editor.text_editor import IntelligentTextEditor


def test_project_manager_update_document_content_persists(tmp_path: Path) -> None:
    config = Config()
    shared = Shared(config)
    pm = ProjectManager(config=config, shared=shared)

    project_dir = tmp_path / "proj"
    assert pm.create_project("Proj", str(project_dir)) is True
    assert pm._current_project is not None
    assert pm._current_project.documents

    doc_id = next(iter(pm._current_project.documents.keys()))

    assert pm.update_document_content(doc_id, "hello") is True
    assert pm.get_document_content(doc_id) == "hello"

    pm.close_project()
    assert pm.open_project(str(project_dir)) is True
    assert pm.get_document_content(doc_id) == "hello"


class _DummyProjectManager:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def update_document_content(self, doc_id: str, content: str) -> bool:  # noqa: D401
        self.calls.append((doc_id, content))
        return True


def test_text_editor_save_and_autosave_use_project_manager(qtbot) -> None:
    config = Config()
    shared = Shared(config)
    editor = IntelligentTextEditor(config=config, shared=shared)
    qtbot.addWidget(editor)

    dummy_pm = _DummyProjectManager()
    editor.set_project_manager(dummy_pm)
    editor.set_document_content("start", "doc1")

    editor.setPlainText("changed")
    assert editor.is_modified() is True

    assert editor.save_document() is True
    assert dummy_pm.calls == [("doc1", "changed")]
    assert editor.is_modified() is False

    editor.setPlainText("changed again")
    assert editor.is_modified() is True

    editor._trigger_auto_save()
    assert dummy_pm.calls[-1] == ("doc1", "changed again")
    assert editor.is_modified() is False
