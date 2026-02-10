from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from PyQt6.QtCore import Qt

from gui.ai.unified_ai_config_dialog import UnifiedAPIConfigWidget


def test_max_tokens_spin_range_allows_large_values(qtbot) -> None:
    widget = UnifiedAPIConfigWidget()
    qtbot.addWidget(widget)
    widget.show()

    spin = widget._max_tokens_spin
    assert spin.maximum() >= 1_000_000

    # Regression: typing a leading digit like "4" should allow 4+ digits (e.g. 4000),
    # not clamp to 3 digits due to a small maximum.
    spin.setValue(2000)
    line_edit = spin.lineEdit()
    assert line_edit is not None

    line_edit.setFocus()
    line_edit.selectAll()
    qtbot.keyClicks(line_edit, "4000")
    qtbot.keyClick(line_edit, Qt.Key.Key_Return)
    qtbot.wait(20)
    assert spin.value() == 4000

    widget.set_config({"provider": "OpenAI", "max_tokens": 1_000_000})
    assert widget.get_config()["max_tokens"] == 1_000_000
