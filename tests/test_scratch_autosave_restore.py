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
from gui.editor.editor_panel import EditorPanel


def _patch_config_dir(config: Config, cfg_dir: Path) -> None:
    cfg_dir.mkdir(parents=True, exist_ok=True)
    # Redirect scratch recovery writes away from the real user config dir.
    config._config_dir = cfg_dir  # type: ignore[attr-defined]
    config._config_file = cfg_dir / "config.json"  # type: ignore[attr-defined]


def test_scratch_autosave_persists_and_restores(tmp_path: Path, qtbot) -> None:
    config = Config()
    _patch_config_dir(config, tmp_path / "cfg")
    shared = Shared(config)

    panel = EditorPanel(config=config, shared=shared)
    qtbot.addWidget(panel)

    editor = panel.get_current_editor()
    assert editor is not None
    assert editor.get_current_document_id() == panel.SCRATCH_DOCUMENT_ID

    editor.insertPlainText("Draft text")
    assert editor.is_modified() is True

    # Force autosave without waiting for the timer.
    editor._trigger_auto_save()

    recovery_path = (tmp_path / "cfg") / "scratch_recovery.txt"
    assert recovery_path.is_file()
    assert recovery_path.read_text(encoding="utf-8") == "Draft text"

    # Simulate a fresh panel/session.
    panel2 = EditorPanel(config=config, shared=shared)
    qtbot.addWidget(panel2)

    restored = panel2.restore_scratch_recovery_if_available()
    assert restored is True

    editor2 = panel2.get_current_editor()
    assert editor2 is not None
    assert editor2.toPlainText() == "Draft text"


def test_flush_all_editors_saves_scratch_and_project(tmp_path: Path, qtbot) -> None:
    config = Config()
    _patch_config_dir(config, tmp_path / "cfg")
    shared = Shared(config)
    pm = ProjectManager(config=config, shared=shared)

    project_dir = tmp_path / "proj"
    assert pm.create_project("Proj", str(project_dir)) is True

    panel = EditorPanel(config=config, shared=shared)
    qtbot.addWidget(panel)
    panel.set_project_manager(pm)

    # Modify scratch first so it won't be reused for project documents.
    scratch = panel._document_tabs.get(panel.SCRATCH_DOCUMENT_ID)
    assert scratch is not None
    scratch.insertPlainText("Scratch")
    assert scratch.is_modified() is True

    # Create a real project-backed document tab.
    docs = pm.get_all_documents()
    assert docs
    doc_id = next(iter(docs.keys()))
    doc = pm.get_document(doc_id)
    assert doc is not None

    assert panel.create_new_document(doc_id, doc.name, doc.content) is True
    editor = panel.get_current_editor()
    assert editor is not None
    assert editor.get_current_document_id() == doc_id

    editor.insertPlainText("Hello")
    assert editor.is_modified() is True

    panel.flush_all_editors()

    assert pm.get_document_content(doc_id).endswith("Hello")
    recovery_path = (tmp_path / "cfg") / "scratch_recovery.txt"
    assert recovery_path.read_text(encoding="utf-8") == "Scratch"
