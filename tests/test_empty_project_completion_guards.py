from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from PyQt6.QtTest import QSignalSpy

from application.ai_context import IntelligentContextBuilder
from core.shared import Shared
from gui.services.index_scheduler import IndexScheduler


class _DummyConfig:
    def get(self, section: str, key: str, default=None):
        return default


def test_shared_emits_project_changed_on_clear(qtbot) -> None:
    shared = Shared(_DummyConfig())

    spy = QSignalSpy(shared.projectChanged)
    shared.current_project_path = Path("C:/tmp/project_one")
    shared.current_project_path = None

    assert len(spy) >= 2
    assert spy[-1][0] == ""


def test_shared_treats_empty_string_project_path_as_clear(qtbot) -> None:
    shared = Shared(_DummyConfig())

    spy = QSignalSpy(shared.projectChanged)
    shared.current_project_path = Path("C:/tmp/project_one")
    shared.current_project_path = ""

    assert shared.current_project_path is None
    assert len(spy) >= 2
    assert spy[-1][0] == ""


class _DummyTaskManager:
    def __init__(self) -> None:
        self.cancelled_prefixes: list[str] = []

    def cancel_prefix(self, prefix: str) -> None:
        self.cancelled_prefixes.append(prefix)


class _DummyRagService:
    def __init__(self) -> None:
        self.set_vector_store_calls: list[object | None] = []

    def set_vector_store(self, store) -> None:
        self.set_vector_store_calls.append(store)


class _DummyShared:
    def __init__(self) -> None:
        self.rag_service = _DummyRagService()
        self.vector_store = object()


def test_index_scheduler_unbinds_vector_store_on_empty_project_path(qtbot) -> None:
    task_manager = _DummyTaskManager()
    scheduler = IndexScheduler(task_manager)

    shared = _DummyShared()
    scheduler._shared = shared

    scheduler._on_project_changed("")

    assert scheduler._rag_disabled is True
    assert shared.vector_store is None
    assert shared.rag_service.set_vector_store_calls == [None]
    assert "rag/" in task_manager.cancelled_prefixes


class _RaisingRagService:
    def search_with_like_tokens(self, *args, **kwargs):
        raise AssertionError("RAG search should have been skipped")

    def search_with_context(self, *args, **kwargs):
        raise AssertionError("RAG search should have been skipped")


class _StubContextResult:
    def __init__(self, rag_query: str) -> None:
        self.rag_query = rag_query
        self.detected_entities = []
        self.primary_keywords = []


class _StubCollector:
    def __init__(self, rag_query: str) -> None:
        self._rag_query = rag_query

    def collect_context_for_completion(self, text: str, cursor_position: int):
        return _StubContextResult(self._rag_query)


@pytest.mark.parametrize("rag_query", ["", "默认查询内容", "默认查询", "强制默认查询"])
def test_context_builder_skips_rag_for_empty_or_placeholder_query(rag_query: str) -> None:
    builder = IntelligentContextBuilder(shared=None)
    builder.rag_service = _RaisingRagService()
    builder._intelligent_context_collector = _StubCollector(rag_query)

    result = builder._search_rag_relevant("任意文本", cursor_pos=0, mode="balanced")
    assert result == ""

