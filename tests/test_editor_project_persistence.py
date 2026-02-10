from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from PyQt6.QtWidgets import QWidget

from core.config import Config
from core.project import ProjectManager
from core.shared import Shared
from gui.editor.editor_panel import EditorPanel
from gui.main_window_parts.integrations import MainWindowIntegrationsMixin
from gui.main_window_parts.ui import MainWindowUIMixin


class _DummyWindow(QWidget, MainWindowIntegrationsMixin):
    def __init__(self, project_manager: ProjectManager, editor_panel: EditorPanel) -> None:
        super().__init__()
        self._project_manager = project_manager
        self._editor_panel = editor_panel

    def _on_document_selected(self, document_id: str) -> None:
        doc = self._project_manager.get_document(document_id)
        if not doc:
            raise AssertionError(f"Document not found: {document_id}")
        if not self._editor_panel.switch_to_document(document_id):
            created = self._editor_panel.create_new_document(document_id, doc.name, doc.content)
            assert created is True


class _DummyCenterPanelHost(QWidget, MainWindowUIMixin):
    def __init__(self, config: Config, shared: Shared, project_manager: ProjectManager) -> None:
        super().__init__()
        self._config = config
        self._shared = shared
        self._project_manager = project_manager
        self._ai_manager = None

    def _on_document_modified(self, document_id: str, is_modified: bool) -> None:  # noqa: ARG002
        return None

    def _on_document_saved(self, document_id: str) -> None:  # noqa: ARG002
        return None


def test_main_window_ui_binds_project_manager_to_editor_panel(qtbot) -> None:
    config = Config()
    shared = Shared(config)
    pm = ProjectManager(config=config, shared=shared)

    host = _DummyCenterPanelHost(config=config, shared=shared, project_manager=pm)
    qtbot.addWidget(host)

    panel = host._create_center_panel()
    qtbot.addWidget(panel)

    assert getattr(panel, "_project_manager", None) is pm


def test_editor_panel_autosave_persists_project_documents(tmp_path: Path, qtbot) -> None:
    config = Config()
    config.set("app", "auto_save_interval", 0)
    shared = Shared(config)
    pm = ProjectManager(config=config, shared=shared)

    project_dir = tmp_path / "proj"
    assert pm.create_project("Proj", str(project_dir)) is True

    panel = EditorPanel(config=config, shared=shared)
    qtbot.addWidget(panel)
    panel.set_project_manager(pm)

    window = _DummyWindow(project_manager=pm, editor_panel=panel)
    qtbot.addWidget(window)

    window._open_default_document_after_project_open()

    editor = panel.get_current_editor()
    assert editor is not None

    doc_id = editor.get_current_document_id()
    assert doc_id
    assert doc_id != "default_doc"
    assert "default_doc" not in getattr(panel, "_document_tabs", {})
    assert getattr(editor, "_project_manager", None) is pm

    editor.insertPlainText("Hello")
    assert editor.is_modified() is True
    assert editor._auto_save_timer.isActive() is True

    editor._trigger_auto_save()
    assert pm.get_document_content(doc_id).endswith("Hello")

    editor.insertPlainText(" World")
    assert editor.save_document() is True

    expected = pm.get_document_content(doc_id)
    assert expected.endswith("Hello World")

    pm.close_project()
    assert pm.open_project(str(project_dir)) is True
    assert pm.get_document_content(doc_id) == expected
