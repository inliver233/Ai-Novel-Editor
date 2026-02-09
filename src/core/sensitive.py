from __future__ import annotations

from typing import Any

SENSITIVE_KEYS: set[str] = {
    "api_key",
    "authorization",
    "x-api-key",
    "x-goog-api-key",
}


def sanitize_for_export(value: Any, *, blank: str = "") -> Any:
    """Return a deep-sanitized copy safe for export/logging.

    - Dict keys matching `SENSITIVE_KEYS` (case-insensitive) have their value replaced with `blank`.
    - Containers are copied recursively; primitives are returned as-is.
    """
    if isinstance(value, dict):
        sanitized: dict[Any, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and k.strip().lower() in SENSITIVE_KEYS:
                sanitized[k] = blank
            else:
                sanitized[k] = sanitize_for_export(v, blank=blank)
        return sanitized

    if isinstance(value, list):
        return [sanitize_for_export(v, blank=blank) for v in value]

    if isinstance(value, tuple):
        return tuple(sanitize_for_export(v, blank=blank) for v in value)

    return value

