from __future__ import annotations

import asyncio
import json
import logging

from core.ai_client import AIClient, AIConfig, AIProvider
from core.ai_providers.claude import ClaudeProvider
from core.ai_providers.openai import OpenAIProvider


class _DummyOpenAIConfig:
    def __init__(self, *, model: str = "gpt-4o-mini", endpoint_url: str | None = None) -> None:
        self.api_key = "test-key"
        self.model = model
        self.endpoint_url = endpoint_url
        self.temperature = 0.7
        self.max_tokens = 256
        self.top_p = 0.9


class _DummyClaudeConfig:
    def __init__(
        self, *, model: str = "claude-3-5-sonnet-latest", endpoint_url: str | None = None
    ) -> None:
        self.api_key = "test-key"
        self.model = model
        self.endpoint_url = endpoint_url
        self.temperature = 0.7
        self.max_tokens = 256
        self.top_p = 0.9


async def _collect_sse_events(client: AIClient, chunks: list[bytes]) -> list[tuple[str | None, str]]:
    async def _byte_iter():
        for chunk in chunks:
            yield chunk

    events: list[tuple[str | None, str]] = []
    async for event_name, data_str in client._iter_sse_event_data(_byte_iter()):
        events.append((event_name, data_str))
    return events


def test_openai_endpoint_url_defaults_to_chat_completions() -> None:
    provider = OpenAIProvider(_DummyOpenAIConfig(), logging.getLogger("t"))
    assert provider.get_endpoint_url() == "https://api.openai.com/v1/chat/completions"


def test_openai_build_request_data_includes_stream() -> None:
    provider = OpenAIProvider(_DummyOpenAIConfig(), logging.getLogger("t"))
    data = provider.build_request_data([{"role": "user", "content": "hi"}], stream=True)
    assert data["stream"] is True
    assert data["model"] == "gpt-4o-mini"
    assert data["max_tokens"] == 256


def test_openai_extract_stream_content_reads_choices_delta_content() -> None:
    provider = OpenAIProvider(_DummyOpenAIConfig(), logging.getLogger("t"))
    chunk = {"choices": [{"delta": {"content": "Hello"}}]}
    assert provider.extract_stream_content(chunk) == "Hello"


def test_claude_endpoint_url_defaults_to_messages() -> None:
    provider = ClaudeProvider(_DummyClaudeConfig(), logging.getLogger("t"))
    assert provider.get_endpoint_url() == "https://api.anthropic.com/v1/messages"


def test_claude_build_request_data_includes_stream() -> None:
    provider = ClaudeProvider(_DummyClaudeConfig(), logging.getLogger("t"))
    data = provider.build_request_data([{"role": "user", "content": "hi"}], stream=True)
    assert data["stream"] is True
    assert data["model"] == "claude-3-5-sonnet-latest"
    assert data["max_tokens"] == 256


def test_claude_extract_stream_content_reads_content_block_delta_text() -> None:
    provider = ClaudeProvider(_DummyClaudeConfig(), logging.getLogger("t"))
    chunk = {
        "type": "content_block_delta",
        "delta": {"type": "text_delta", "text": "Hello"},
    }
    assert provider.extract_stream_content(chunk) == "Hello"
    assert provider.extract_stream_content({"type": "message_start"}) is None


def test_ai_client_sse_parser_handles_chunk_boundaries_openai_like() -> None:
    client = AIClient(AIConfig(provider=AIProvider.OPENAI, model="gpt-4o-mini"))

    raw = (
        "data: {\"choices\":[{\"delta\":{\"content\":\"Hel\"}}]}\n\n"
        "data: {\"choices\":[{\"delta\":{\"content\":\"lo\"}}]}\n\n"
        "data: [DONE]\n\n"
    ).encode("utf-8")

    chunks = [
        raw[:7],
        raw[7:23],
        raw[23:61],
        raw[61:77],
        raw[77:],
    ]

    events = asyncio.run(_collect_sse_events(client, chunks))
    assert [d for _e, d in events][-1].strip() == "[DONE]"

    provider = OpenAIProvider(_DummyOpenAIConfig(), logging.getLogger("t"))
    out: list[str] = []
    for _event, data_str in events:
        data_str = data_str.strip()
        if data_str == "[DONE]":
            break
        chunk_data = json.loads(data_str)
        text = provider.extract_stream_content(chunk_data)
        if text:
            out.append(text)

    assert "".join(out) == "Hello"


def test_ai_client_sse_parser_handles_event_and_data_lines_claude_like() -> None:
    client = AIClient(AIConfig(provider=AIProvider.CLAUDE, model="claude-3-5-sonnet-latest"))

    raw = (
        "event: message_start\n"
        "data: {\"type\":\"message_start\",\"message\":{\"id\":\"msg_123\"}}\n\n"
        "event: content_block_delta\n"
        "data: {\"type\":\"content_block_delta\",\"delta\":{\"type\":\"text_delta\",\"text\":\"Hello\"}}\n\n"
        "event: content_block_delta\n"
        "data: {\"type\":\"content_block_delta\",\"delta\":{\"type\":\"text_delta\",\"text\":\" world\"}}\n\n"
        "event: message_stop\n"
        "data: {\"type\":\"message_stop\"}\n\n"
    ).encode("utf-8")

    chunks = [raw[:10], raw[10:55], raw[55:120], raw[120:170], raw[170:]]
    events = asyncio.run(_collect_sse_events(client, chunks))

    assert events[0][0] == "message_start"
    assert json.loads(events[1][1])["type"] == "content_block_delta"

    provider = ClaudeProvider(_DummyClaudeConfig(), logging.getLogger("t"))
    out: list[str] = []
    for _event, data_str in events:
        chunk_data = json.loads(data_str)
        text = provider.extract_stream_content(chunk_data)
        if text:
            out.append(text)

    assert "".join(out) == "Hello world"

