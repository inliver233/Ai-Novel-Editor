from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainter, QPixmap, QTextCursor

from core.config import Config
from core.shared import Shared
from gui.editor.text_editor import IntelligentTextEditor


def test_deep_ghost_overlay_uses_cursor_rect_without_double_content_offset(
    qtbot, monkeypatch
) -> None:
    config = Config()
    shared = Shared(config)

    editor = IntelligentTextEditor(config=config, shared=shared)
    qtbot.addWidget(editor)
    editor.setFixedSize(520, 240)
    editor.show()
    editor.setFocus()

    editor.setPlainText("\n".join([f"Line {i} 你好世界" for i in range(300)]))
    qtbot.wait(50)

    # Scroll to the bottom so contentOffset is non-zero (negative y).
    vbar = editor.verticalScrollBar()
    assert vbar.maximum() > 0
    vbar.setValue(vbar.maximum())
    qtbot.wait(50)

    # Place caret at the end and activate ghost text at that position.
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.setTextCursor(cursor)

    anchor_pos = editor.textCursor().position()
    anchor_rect = editor.cursorRect(editor.textCursor())
    assert anchor_rect.isNull() is False

    editor.set_ghost_text("GHOST", anchor_pos)
    ghost = getattr(editor, "_ghost_completion", None)
    assert ghost is not None

    # Simulate a scrolled contentOffset without depending on platform-specific Qt internals.
    # The regression was caused by applying contentOffset twice when using cursorRect fallback.
    monkeypatch.setattr(editor, "contentOffset", lambda: QPointF(0.0, -120.0), raising=False)

    # Force cursorRect fallback path by making layout calculator return y==0.
    ghost.layout_calculator.calculate_ghost_position = lambda _b, _p: QRectF(0, 0, 1, 10)  # type: ignore[attr-defined]

    rendered_positions: list[QRectF] = []

    def _record(_painter, _text, rect, _font) -> None:
        rendered_positions.append(QRectF(rect))

    ghost.rendering_engine.render_ghost_text_simple = _record  # type: ignore[attr-defined]

    pixmap = QPixmap(editor.viewport().size())
    pixmap.fill()
    painter = QPainter(pixmap)
    ghost.render_ghost_text(painter)
    painter.end()

    assert rendered_positions, "Expected ghost overlay render to produce at least one draw call"
    first = rendered_positions[0]

    # The overlay should be anchored at the caret rect in viewport coordinates (no extra contentOffset).
    assert abs(float(first.y()) - float(anchor_rect.y())) <= 2.0
    assert 0.0 <= float(first.y()) <= float(editor.viewport().height())
