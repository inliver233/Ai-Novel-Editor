from __future__ import annotations

import sys
import types

from core.improved_context_extractor import ImprovedContextExtractor
from tests.fixtures.golden_data import load_golden_story
from tests.golden.snapshot_utils import assert_golden


def _format_rag_query_context(context: dict) -> str:
    lines = [
        f"query: {context['query']}",
        f"context_summary: {context['context_summary']}",
        f"relevance_score: {context['relevance_score']:.4f}",
        f"primary_keywords: {', '.join(context['primary_keywords'])}",
        f"secondary_keywords: {', '.join(context['secondary_keywords'])}",
        f"context_length: {context['context_length']}",
        f"segment_count: {context['segment_count']}",
    ]
    return "\n".join(lines)


def test_rag_query_planning_snapshot(monkeypatch) -> None:
    for module_name in list(sys.modules):
        if module_name.startswith("jieba"):
            sys.modules.pop(module_name, None)
    monkeypatch.setitem(sys.modules, "jieba", types.ModuleType("jieba"))

    text = load_golden_story()
    cursor_position = len(text)

    extractor = ImprovedContextExtractor()
    extracted = extractor.extract_context_for_completion(text, cursor_position)
    rag_context = extractor.get_rag_query_context(extracted)

    assert_golden("rag_query_planning.txt", _format_rag_query_context(rag_context))
