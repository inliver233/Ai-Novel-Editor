from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from PyQt6.QtCore import Qt

from core.config import Config
from core.shared import Shared
from gui.editor.text_editor import IntelligentTextEditor


def test_streaming_ghost_preview_does_not_overwrite_document(qtbot) -> None:
    config = Config()
    shared = Shared(config)

    editor = IntelligentTextEditor(config=config, shared=shared)
    qtbot.addWidget(editor)
    editor.show()
    editor.setFocus()

    editor.set_document_content("Hello ", document_id="doc1")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    anchor_pos = editor.textCursor().position()
    original_text = editor.toPlainText()

    context = {"request_id": "r1", "task_key": "t1", "cursor_position": anchor_pos}
    editor._smart_completion.update_streaming_ai_completion("World", context)

    ghost = getattr(editor, "_ghost_completion", None)
    qtbot.waitUntil(lambda: getattr(ghost, "_current_ghost_text", "") == "World", timeout=1500)

    assert editor.toPlainText() == original_text
    assert editor.textCursor().position() == anchor_pos

    # Accept preview with Tab.
    qtbot.keyClick(editor, Qt.Key.Key_Tab)
    qtbot.wait(50)

    assert editor.toPlainText() == "Hello World"
    assert editor.textCursor().position() == len("Hello World")


def test_streaming_preview_stops_when_caret_moves(qtbot) -> None:
    config = Config()
    shared = Shared(config)

    editor = IntelligentTextEditor(config=config, shared=shared)
    qtbot.addWidget(editor)
    editor.show()
    editor.setFocus()

    editor.set_document_content("ABC", document_id="doc1")
    cursor = editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    anchor_pos = editor.textCursor().position()
    context = {"request_id": "r1", "task_key": "t1", "cursor_position": anchor_pos}

    editor._smart_completion.update_streaming_ai_completion("X", context)
    qtbot.wait(50)

    # Move caret away from the anchor position.
    cursor = editor.textCursor()
    cursor.setPosition(0)
    editor.setTextCursor(cursor)

    # Further chunks should stop streaming rendering instead of jumping to the new caret position.
    editor._smart_completion.update_streaming_ai_completion("Y", context)
    qtbot.wait(50)

    ghost = getattr(editor, "_ghost_completion", None)
    assert not bool(getattr(ghost, "_current_ghost_text", ""))
    assert editor.toPlainText() == "ABC"
