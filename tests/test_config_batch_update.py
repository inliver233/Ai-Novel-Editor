from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")

from PyQt6.QtCore import QCoreApplication  # noqa: E402

from core.config import Config  # noqa: E402


def test_config_batch_update_saves_once(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    # Ensure Qt has an application instance for QSettings/QStandardPaths.
    QCoreApplication.instance() or QCoreApplication([])

    monkeypatch.setenv("ANE_PORTABLE", "1")
    monkeypatch.chdir(tmp_path)

    config = Config()

    save_calls = {"n": 0}

    def _fake_save() -> bool:
        save_calls["n"] += 1
        return True

    monkeypatch.setattr(config, "_save_config", _fake_save)

    with config.batch_update():
        config.set("ai", "model", "gpt-3.5-turbo")
        config.set("ai", "timeout", 31)

    assert save_calls["n"] == 1

