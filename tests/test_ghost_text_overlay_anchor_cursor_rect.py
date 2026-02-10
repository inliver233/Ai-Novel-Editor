from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QPainter, QPixmap, QTextCursor

from core.config import Config
from core.shared import Shared
from gui.editor.text_editor import IntelligentTextEditor


def test_ghost_overlay_anchors_to_cursor_rect_even_if_layout_calculator_is_wrong(qtbot) -> None:
    config = Config()
    shared = Shared(config)

    editor = IntelligentTextEditor(config=config, shared=shared)
    qtbot.addWidget(editor)
    editor.setFixedSize(520, 260)
    editor.show()
    editor.setFocus()

    editor.setPlainText("\n".join([f"Line {i} 内容" for i in range(50)]))
    qtbot.wait(50)

    # Place caret on a lower visible line to get a non-zero y anchor.
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.Start)
    for _ in range(8):
        cursor.movePosition(QTextCursor.MoveOperation.Down)
    editor.setTextCursor(cursor)
    qtbot.wait(20)

    anchor_pos = editor.textCursor().position()
    anchor_rect = editor.cursorRect(editor.textCursor())
    assert anchor_rect.isNull() is False
    assert int(anchor_rect.y()) > 0

    editor.set_ghost_text("GHOST", anchor_pos)
    ghost = getattr(editor, "_ghost_completion", None)
    assert ghost is not None

    # Make doc-layout calculator return a clearly incorrect location.
    wrong_rect = QRectF(0, float(anchor_rect.y() + 120), 1, float(anchor_rect.height()))
    ghost.layout_calculator.calculate_ghost_position = lambda _b, _p: wrong_rect  # type: ignore[attr-defined]

    rendered_positions: list[QRectF] = []

    def _record(_painter, _text, rect, _font) -> None:
        rendered_positions.append(QRectF(rect))

    ghost.rendering_engine.render_ghost_text_simple = _record  # type: ignore[attr-defined]

    pixmap = QPixmap(editor.viewport().size())
    pixmap.fill()
    painter = QPainter(pixmap)
    ghost.render_ghost_text(painter)
    painter.end()

    assert rendered_positions
    first = rendered_positions[0]

    # Must anchor to caret (cursorRect), not to the wrong layout_calculator position.
    assert abs(float(first.y()) - float(anchor_rect.y())) <= 2.0

