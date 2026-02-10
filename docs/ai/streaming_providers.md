# Streaming providers (SSE): OpenAI / Anthropic / Gemini

Last verified: 2026-02-10

This project implements streaming via Server-Sent Events (SSE) and extracts incremental text via provider strategies.

## Common SSE notes

- SSE frames are separated by a blank line (`\n\n`). Each frame may include `event:` and one or more `data:` lines.
- Networks/proxies can split or coalesce frames arbitrarily at the byte level, so the client must buffer and parse by newline boundaries (not by “chunk” boundaries).

Implementation notes:

- `src/core/ai_client.py`: `_iter_sse_event_data()` parses SSE from arbitrary byte chunks and yields `(event, data)` tuples.
- Provider-specific text extraction lives in `src/core/ai_providers/*` via `extract_stream_content()`.

## OpenAI (Chat Completions API)

- Endpoint: `POST https://api.openai.com/v1/chat/completions`
- Headers: `Authorization: Bearer <api_key>`, `Content-Type: application/json`
- Request: `model`, `messages`, `stream: true`
  - Standard models: `max_tokens`
  - Reasoning models (as used by this app for `o1/o3/o4*`): `max_completion_tokens`
  - Optional: `stream_options: { include_usage: true }`
- Response: `text/event-stream`
  - Each SSE frame is `data: { ...json... }`
  - Stream terminates with: `data: [DONE]`
- Incremental text extraction used by this app: `choices[0].delta.content`

## Anthropic (Claude Messages API)

- Endpoint: `POST https://api.anthropic.com/v1/messages`
- Headers: `x-api-key: <api_key>`, `anthropic-version: <date>` (required)
- Request: `model`, `max_tokens`, `stream: true`, `messages`; optional `system`, `temperature`, `tools`
- Response: `text/event-stream` with explicit `event:` names.
  - Typical event sequence: `message_start` → `content_block_start` → `content_block_delta` → … → `message_stop`
  - Content deltas are sent as JSON objects with a top-level `type` field, e.g. `{"type":"content_block_delta","delta":{"type":"text_delta","text":"..."}}`
- Incremental text extraction used by this app: when `type == "content_block_delta"`, use `delta.text` (ignoring non-text deltas).

## Gemini (Google AI for Developers — Generative Language API v1beta)

- Endpoint: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse`
  - `alt=sse` is required to receive SSE responses.
- Auth: `x-goog-api-key: <api_key>` header (or `key=<api_key>` query parameter)
- Request: `contents` (role + parts), `generationConfig` (`temperature`, `topP`, `maxOutputTokens`, etc.)
- Response: `text/event-stream` with `data: { ...json... }` frames (no `[DONE]` sentinel; the stream ends when the server closes).
- Incremental text extraction used by this app: `candidates[0].content.parts[].text` (ignoring parts marked `thought: true`).

## References (official)

- OpenAI — Chat Completions API: https://platform.openai.com/docs/api-reference/chat/create-chat-completion
- OpenAI — Streaming responses (Responses API guide): https://platform.openai.com/docs/guides/streaming-responses
- Anthropic — Streaming: https://docs.anthropic.com/en/docs/build-with-claude/streaming
- Google AI for Developers — `models.streamGenerateContent` (SSE example): https://ai.google.dev/api/rest/v1beta/models/streamGenerateContent

