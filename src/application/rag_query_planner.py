"""
RAG query planning (application layer).

Goal: keep storage/retrieval layers (e.g. SQLiteVectorStore) free of query planning,
keyword extraction, and AI/network calls.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence

logger = logging.getLogger(__name__)


_PUNCTUATION_RE = re.compile(r"[，。！？、,.\s]+")
_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def _unique_in_order(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _default_stop_words() -> set[str]:
    # A lightweight list (avoid over-filtering).
    return {
        "的",
        "是",
        "在",
        "有",
        "和",
        "与",
        "了",
        "着",
        "过",
        "等",
        "主题",
        "内容",
        "关于",
        "从",
        "被",
        "到",
        "他",
        "她",
        "我",
        "你",
        "它",
        "这",
        "那",
        "一个",
        "什么",
        "怎么",
        "为什么",
        "因为",
        "所以",
        "但是",
        "然后",
        "现在",
        "时候",
        "地方",
        "东西",
        "事情",
        "问题",
        "方面",
        "情况",
    }


@dataclass(frozen=True)
class RAGQueryPlan:
    raw_query: str
    cleaned_query: str
    like_tokens: List[str]


class RAGQueryPlanner:
    def __init__(self, *, use_jieba: bool = True, stop_words: Sequence[str] | None = None) -> None:
        self._use_jieba = use_jieba
        self._stop_words = set(stop_words) if stop_words is not None else _default_stop_words()

    def plan(self, query_text: str, *, max_like_tokens: int = 3) -> RAGQueryPlan:
        cleaned = self._clean_query(query_text)
        like_tokens = self.plan_like_tokens(query_text, max_tokens=max_like_tokens)
        return RAGQueryPlan(raw_query=query_text, cleaned_query=cleaned, like_tokens=like_tokens)

    def plan_like_tokens(self, query_text: str, *, max_tokens: int = 3) -> List[str]:
        cleaned = self._clean_query(query_text)
        if len(cleaned) < 2:
            return []

        # Short query: use as-is.
        if len(cleaned) <= 6 and cleaned not in self._stop_words:
            return [cleaned]

        # Try jieba first (if available), then fallback to simple n-grams.
        tokens: List[str] = []
        if self._use_jieba:
            tokens = self._try_jieba_tokens(cleaned)

        if not tokens:
            tokens = self._fallback_ngram_tokens(cleaned)

        tokens = [t for t in tokens if 2 <= len(t) <= 6 and t not in self._stop_words]
        tokens = _unique_in_order(tokens)
        return tokens[: max(0, int(max_tokens))]

    def _clean_query(self, query_text: str) -> str:
        return _PUNCTUATION_RE.sub("", (query_text or "")).strip()

    def _try_jieba_tokens(self, cleaned: str) -> List[str]:
        try:
            import jieba  # type: ignore

            # Ensure deterministic behavior and avoid noisy logs.
            try:
                jieba.setLogLevel(logging.WARNING)
            except Exception:
                pass

            words = list(jieba.cut(cleaned, cut_all=False))
            return [w.strip() for w in words if w and w.strip()]
        except Exception as e:
            logger.debug("jieba unavailable for query planning: %s", e)
            return []

    def _fallback_ngram_tokens(self, cleaned: str) -> List[str]:
        chars = _CHINESE_CHAR_RE.findall(cleaned)
        if len(chars) < 2:
            return []

        # Prefer 2-grams and 3-grams; keep order.
        tokens: List[str] = []
        for i in range(len(chars) - 1):
            tokens.append(chars[i] + chars[i + 1])
        for i in range(len(chars) - 2):
            tokens.append(chars[i] + chars[i + 1] + chars[i + 2])
        return tokens

