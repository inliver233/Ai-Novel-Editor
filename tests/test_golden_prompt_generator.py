from __future__ import annotations

import sys
import types
import importlib.util
from pathlib import Path

from tests.fixtures.golden_data import load_golden_story
from tests.golden.snapshot_utils import assert_golden


def _install_dummy_pyqt(monkeypatch) -> None:
    if "PyQt6" in sys.modules:
        return

    class _DummySignal:
        def connect(self, *args, **kwargs) -> None:
            return None

        def emit(self, *args, **kwargs) -> None:
            return None

    class QObject:  # noqa: D401 - dummy
        def __init__(self, *args, **kwargs) -> None:
            super().__init__()

    def pyqtSignal(*args, **kwargs):
        return _DummySignal()

    def pyqtSlot(*args, **kwargs):
        def decorator(func):
            return func

        return decorator

    class QTimer:
        def __init__(self, *args, **kwargs) -> None:
            self.timeout = _DummySignal()

        def setSingleShot(self, *args, **kwargs) -> None:
            return None

        def start(self, *args, **kwargs) -> None:
            return None

    class QThread:
        def __init__(self, *args, **kwargs) -> None:
            return None

    class QWidget:
        def __init__(self, *args, **kwargs) -> None:
            return None

    class QMessageBox:
        pass

    qtcore = types.ModuleType("PyQt6.QtCore")
    qtcore.QObject = QObject
    qtcore.pyqtSignal = pyqtSignal
    qtcore.pyqtSlot = pyqtSlot
    qtcore.QTimer = QTimer
    qtcore.QThread = QThread

    qtwidgets = types.ModuleType("PyQt6.QtWidgets")
    qtwidgets.QWidget = QWidget
    qtwidgets.QMessageBox = QMessageBox

    pyqt6 = types.ModuleType("PyQt6")

    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qtcore)
    monkeypatch.setitem(sys.modules, "PyQt6.QtWidgets", qtwidgets)


def _build_context_data(text: str) -> dict:
    return {
        "text_context": {
            "before": text,
            "after": "",
            "full_context": text,
            "cursor_line": text.splitlines()[-1],
        },
        "codex_context": [
            {"title": "季遥", "type": "CHARACTER"},
        ],
        "rag_context": "",
        "user_preferences": {},
        "document_metadata": {},
        "scene_analysis": {},
    }


def test_prompt_generator_snapshot(monkeypatch) -> None:
    _install_dummy_pyqt(monkeypatch)
    repo_root = Path(__file__).resolve().parents[1]
    module_path = repo_root / "src" / "gui" / "ai" / "enhanced_ai_manager.py"
    spec = importlib.util.spec_from_file_location("golden_enhanced_ai_manager", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    DynamicPromptGenerator = getattr(module, "DynamicPromptGenerator")

    text = load_golden_story()
    context_data = _build_context_data(text)

    generator = DynamicPromptGenerator(shared=None, config=None)
    generator.prompt_manager = None  # force deterministic simple prompt path

    prompt = generator.generate_prompt(
        context_data=context_data,
        user_tags=["写实"],
        completion_type="text",
        mode="balanced",
    )

    assert_golden("prompt_generator.txt", prompt)
