from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from core.config import Config
from core.project import ProjectManager
from core.shared import Shared
from gui.main_window import MainWindow


def test_main_window_smoke(qtbot: "pytestqt.qtbot.QtBot") -> None:
    config = Config()
    shared = Shared(config)
    project_manager = ProjectManager(config, shared)

    window = MainWindow(config, shared, project_manager)
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(50)
    window.close()
