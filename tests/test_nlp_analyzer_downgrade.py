from __future__ import annotations

import pytest

from core import nlp_analyzer


def test_nltk_missing_data_falls_back_to_regex(monkeypatch: pytest.MonkeyPatch) -> None:
    if not nlp_analyzer.NLTK_AVAILABLE:
        pytest.skip("nltk not installed")

    monkeypatch.setattr(
        nlp_analyzer.nltk.data,
        "find",
        lambda *args, **kwargs: (_ for _ in ()).throw(LookupError("missing")),
    )
    monkeypatch.setattr(
        nlp_analyzer.nltk,
        "download",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("download should not be called")),
    )

    analyzer = nlp_analyzer.NLPAnalyzer(backend=nlp_analyzer.NLPBackend.NLTK)
    assert analyzer.initialized is True
    assert analyzer.backend == nlp_analyzer.NLPBackend.REGEX_ONLY

