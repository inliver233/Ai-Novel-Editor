from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from PyQt6.QtWidgets import QMainWindow, QWidget

from core.config import Config
from core.shared import Shared
from gui.editor.editor_panel import EditorPanel
from gui.status.status_bar import EnhancedStatusBar


def _assert_children_not_vertically_clipped(parent: QWidget, children: list[QWidget]) -> None:
    assert parent.height() > 0
    for child in children:
        assert child.height() > 0
        assert child.height() >= child.minimumSizeHint().height() - 2


def test_enhanced_status_bar_not_fixed_height_and_not_clipped(qtbot) -> None:
    window = QMainWindow()
    qtbot.addWidget(window)

    status_bar = EnhancedStatusBar(window)
    window.setStatusBar(status_bar)
    window.resize(900, 200)
    window.show()

    qtbot.wait(50)

    assert status_bar.maximumHeight() > status_bar.minimumHeight()

    widgets = [
        status_bar._main_message,
        status_bar._cursor_position_label,
        status_bar._progress_indicator,
        status_bar._word_count_label,
        status_bar._char_count_label,
        status_bar._paragraph_count_label,
        status_bar._doc_status_label,
        status_bar._ai_status_widget,
    ]
    _assert_children_not_vertically_clipped(status_bar, widgets)


def test_editor_panel_status_frame_not_clipped(qtbot) -> None:
    config = Config()
    shared = Shared(config)

    panel = EditorPanel(config, shared)
    qtbot.addWidget(panel)

    panel.resize(900, 600)
    panel.show()
    qtbot.wait(50)

    status_frame = panel._cursor_label.parentWidget()
    assert status_frame is not None

    assert status_frame.maximumHeight() > status_frame.minimumHeight()

    children = [panel._cursor_label, panel._word_count_label, panel._modified_label]
    _assert_children_not_vertically_clipped(status_frame, children)

    editor = panel.get_current_editor()
    if editor and hasattr(editor, "_status_indicator") and editor._status_indicator:
        _assert_children_not_vertically_clipped(status_frame, [editor._status_indicator])

