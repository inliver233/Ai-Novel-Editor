from __future__ import annotations

from core.sensitive import sanitize_for_export


def test_sanitize_for_export_blanks_sensitive_keys() -> None:
    original = {
        "api_key": "secret-1",
        "Authorization": "Bearer secret-2",
        "nested": {"x-api-key": "secret-3", "ok": 1},
        "items": [{"x-goog-api-key": "secret-4"}, {"ok": 2}],
    }

    sanitized = sanitize_for_export(original)

    assert sanitized["api_key"] == ""
    assert sanitized["Authorization"] == ""
    assert sanitized["nested"]["x-api-key"] == ""
    assert sanitized["nested"]["ok"] == 1
    assert sanitized["items"][0]["x-goog-api-key"] == ""
    assert sanitized["items"][1]["ok"] == 2

    # Original must remain unchanged
    assert original["api_key"] == "secret-1"
    assert original["Authorization"] == "Bearer secret-2"

