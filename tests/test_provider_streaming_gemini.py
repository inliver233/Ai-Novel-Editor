from __future__ import annotations

import logging

from core.ai_providers.gemini import GeminiProvider


class _DummyAIConfig:
    def __init__(self, *, model: str = "gemini-2.0-flash", endpoint_url: str | None = None) -> None:
        self.api_key = "test-key"
        self.model = model
        self.endpoint_url = endpoint_url
        self.temperature = 0.7
        self.max_tokens = 256
        self.top_p = 0.9


def test_gemini_stream_endpoint_defaults_to_stream_generate_content() -> None:
    provider = GeminiProvider(_DummyAIConfig(model="gemini-2.0-flash"), logging.getLogger("t"))
    assert provider.get_stream_endpoint_url() == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse"
    )


def test_gemini_stream_endpoint_rewrites_generate_content_and_sets_alt_sse() -> None:
    cfg = _DummyAIConfig(
        model="gemini-2.0-flash",
        endpoint_url="https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
    )
    provider = GeminiProvider(cfg, logging.getLogger("t"))
    assert provider.get_stream_endpoint_url() == (
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent?alt=sse"
    )


def test_gemini_extract_stream_content_yields_incremental_text() -> None:
    provider = GeminiProvider(_DummyAIConfig(), logging.getLogger("t"))

    chunk1 = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"text": "Hello"}],
                }
            }
        ]
    }
    assert provider.extract_stream_content(chunk1) == "Hello"

    chunk2 = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [{"text": " world"}],
                }
            }
        ]
    }
    assert provider.extract_stream_content(chunk2) == " world"

    chunk3 = {
        "candidates": [
            {
                "content": {
                    "role": "model",
                    "parts": [
                        {"text": "THOUGHT", "thought": True},
                        {"text": "Answer"},
                    ],
                }
            }
        ]
    }
    assert provider.extract_stream_content(chunk3) == "Answer"

