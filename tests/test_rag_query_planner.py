from __future__ import annotations

from application.rag_query_planner import RAGQueryPlanner


def test_plan_like_tokens_strips_punctuation() -> None:
    planner = RAGQueryPlanner(use_jieba=False)
    tokens = planner.plan_like_tokens("江湖？！！", max_tokens=3)
    assert tokens == ["江湖"]


def test_plan_like_tokens_short_query_returns_itself() -> None:
    planner = RAGQueryPlanner(use_jieba=False)
    assert planner.plan_like_tokens("武侠", max_tokens=3) == ["武侠"]


def test_plan_like_tokens_respects_max_tokens() -> None:
    planner = RAGQueryPlanner(use_jieba=False)
    tokens = planner.plan_like_tokens("张三在江湖遇到李四然后发生了一些事情", max_tokens=2)
    assert 0 < len(tokens) <= 2
    assert all(t.strip() and len(t) >= 2 for t in tokens)

