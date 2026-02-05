from __future__ import annotations

import os
import sys
import unittest

try:
    from PyQt6.QtWidgets import QApplication
except ImportError as exc:  # pragma: no cover - optional dependency
    raise unittest.SkipTest(f"PyQt6 not available: {exc}") from exc

from core.config import Config
from core.project import ProjectManager
from core.shared import Shared
from gui.main_window import MainWindow


def _get_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        app = QApplication(sys.argv)
    return app


def test_main_window_smoke() -> None:
    app = _get_app()
    config = Config()
    shared = Shared(config)
    project_manager = ProjectManager(config, shared)

    window = MainWindow(config, shared, project_manager)
    window.show()
    app.processEvents()
    window.close()
    app.processEvents()
