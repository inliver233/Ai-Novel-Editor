from __future__ import annotations

import os
from pathlib import Path

import pytest
from PyQt6.QtWidgets import QMenu

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from gui.menus.menu_bar import MenuBar


class _DummyConfig:
    def __init__(self, recent_projects: list[str]) -> None:
        self._data = {
            "project": {
                "recent_projects": list(recent_projects),
                "max_recent_projects": 10,
            }
        }

    def get(self, section: str, key: str | None = None, default=None):
        if key is None:
            return self._data.get(section, default)
        return self._data.get(section, {}).get(key, default)


def test_recent_projects_menu_emits_open_recent(qtbot: "pytestqt.qtbot.QtBot") -> None:
    p1 = str(Path("C:/tmp/project_one"))
    p2 = str(Path("D:/work/project_two"))
    config = _DummyConfig([p1, p2])

    bar = MenuBar(config)
    menu = QMenu()
    bar._populate_recent_projects(menu)

    actions = [a for a in menu.actions() if not a.isSeparator()]
    assert len(actions) >= 3  # 2 recents + clear

    with qtbot.waitSignal(bar.actionTriggered, timeout=1000) as sig:
        actions[0].trigger()

    assert sig.args[0] == "open_recent"
    assert sig.args[1]["project_path"] in {p1, p2}


def test_recent_projects_menu_emits_clear_recent(qtbot: "pytestqt.qtbot.QtBot") -> None:
    config = _DummyConfig([str(Path("C:/tmp/project_one"))])

    bar = MenuBar(config)
    menu = QMenu()
    bar._populate_recent_projects(menu)

    actions = [a for a in menu.actions() if not a.isSeparator()]
    clear_action = actions[-1]
    assert "清除最近项目" in clear_action.text()

    with qtbot.waitSignal(bar.actionTriggered, timeout=1000) as sig:
        clear_action.trigger()

    assert sig.args[0] == "clear_recent"

