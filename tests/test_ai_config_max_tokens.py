from __future__ import annotations

from gui.ai.unified_ai_config_dialog import UnifiedAPIConfigWidget


def test_max_tokens_spinbox_allows_large_values(qtbot) -> None:
    widget = UnifiedAPIConfigWidget()
    qtbot.addWidget(widget)

    spin = widget._max_tokens_spin
    assert spin.maximum() >= 1_000_000

    spin.lineEdit().setText("400000")
    spin.interpretText()
    assert spin.value() == 400_000

    spin.lineEdit().setText("1000000")
    spin.interpretText()
    assert spin.value() == 1_000_000

