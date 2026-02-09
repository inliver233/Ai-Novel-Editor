from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from core.config import Config
from core.shared import Shared
from gui.editor.editor_panel import EditorPanel


def test_editor_panel_default_doc_is_empty(qtbot: "pytestqt.qtbot.QtBot") -> None:
    config = Config()
    shared = Shared(config)

    panel = EditorPanel(config, shared)
    qtbot.addWidget(panel)

    editor = panel.get_current_editor()
    assert editor is not None

    text = editor.toPlainText()
    assert text.strip() == ""
    assert "TODO" not in text
    assert "我的小说" not in text

