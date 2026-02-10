from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from gui.editor.smart_completion_manager import TypedStreamingGhostTextController


def test_typed_streaming_renderer_types_in_order(qtbot) -> None:
    rendered: list[str] = []

    def _render(text: str) -> None:
        rendered.append(text)

    def _hide() -> None:
        return None

    controller = TypedStreamingGhostTextController(
        render=_render,
        hide=_hide,
        flush_interval_ms=1,
        max_chars_per_tick=1,
    )

    controller.on_chunk("abc", {"request_id": "r1", "task_key": "t1"})

    qtbot.waitUntil(lambda: bool(rendered) and rendered[-1] == "abc", timeout=1000)
    assert rendered == ["a", "ab", "abc"]


def test_typed_streaming_renderer_cancel_stops_updates(qtbot) -> None:
    rendered: list[str] = []

    def _render(text: str) -> None:
        rendered.append(text)

    def _hide() -> None:
        rendered.append("<hide>")

    controller = TypedStreamingGhostTextController(
        render=_render,
        hide=_hide,
        flush_interval_ms=10,
        max_chars_per_tick=1,
    )

    controller.on_chunk("ab", {"request_id": "r1"})
    qtbot.waitUntil(lambda: bool(rendered) and rendered[-1] == "a", timeout=1000)

    controller.cancel()
    qtbot.wait(40)

    assert rendered.count("ab") == 0


def test_typed_streaming_renderer_ignores_stale_request_id(qtbot) -> None:
    rendered: list[str] = []

    def _render(text: str) -> None:
        rendered.append(text)

    def _hide() -> None:
        return None

    controller = TypedStreamingGhostTextController(
        render=_render,
        hide=_hide,
        flush_interval_ms=1,
        max_chars_per_tick=10,
    )

    controller.on_chunk("X", {"request_id": "r2"})
    qtbot.waitUntil(lambda: bool(rendered) and rendered[-1] == "X", timeout=1000)

    controller.on_chunk("Y", {"request_id": "r1"})
    qtbot.wait(20)

    assert rendered[-1] == "X"
