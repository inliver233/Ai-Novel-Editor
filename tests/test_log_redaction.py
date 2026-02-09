from __future__ import annotations

from core.log import redact_sensitive_text


def test_redact_sensitive_text_removes_key_patterns() -> None:
    text = "api_key=sk-1234567890 Bearer secret-token x-api-key=1 x-goog-api-key=2"
    redacted = redact_sensitive_text(text)

    assert "api_key" not in redacted
    assert "sk-" not in redacted
    assert "Bearer " not in redacted
    assert "x-api-key" not in redacted.lower()
    assert "x-goog-api-key" not in redacted.lower()


def test_redact_sensitive_text_truncates_long_messages() -> None:
    redacted = redact_sensitive_text("a" * 2000)
    assert "<TRUNCATED" in redacted

