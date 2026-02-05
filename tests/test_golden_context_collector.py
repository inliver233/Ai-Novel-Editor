from __future__ import annotations

import sys
import types

from core.intelligent_context_collector import IntelligentContextCollector
from tests.fixtures.golden_data import load_golden_story
from tests.golden.snapshot_utils import assert_golden


def _format_result(result) -> str:
    lines = [
        f"trigger_position: {result.trigger_position}",
        "full_context:",
        result.full_context,
        f"primary_keywords: {', '.join(result.primary_keywords)}",
        f"secondary_keywords: {', '.join(result.secondary_keywords)}",
        f"detected_entities: {', '.join(result.detected_entities)}",
        f"rag_query: {result.rag_query}",
        f"context_summary: {result.context_summary}",
        f"relevance_score: {result.relevance_score:.4f}",
        f"collection_method: {result.collection_method}",
    ]
    return "\n".join(lines)


def test_context_collector_snapshot(monkeypatch) -> None:
    # Force deterministic fallback keyword extraction (avoid jieba variations)
    for module_name in list(sys.modules):
        if module_name.startswith("jieba"):
            sys.modules.pop(module_name, None)
    monkeypatch.setitem(sys.modules, "jieba", types.ModuleType("jieba"))

    text = load_golden_story()
    cursor_position = len(text)

    collector = IntelligentContextCollector()
    result = collector.collect_context_for_completion(text, cursor_position)

    assert_golden("context_collector.txt", _format_result(result))
