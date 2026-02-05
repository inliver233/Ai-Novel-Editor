from __future__ import annotations

from pathlib import Path


GOLDEN_DIR = Path(__file__).resolve().parent


def _normalize(content: str) -> str:
    text = content.replace("\r\n", "\n").rstrip()
    return f"{text}\n" if text else ""


def read_golden(name: str) -> str:
    return _normalize((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def assert_golden(name: str, content: str) -> None:
    expected = read_golden(name)
    actual = _normalize(content)
    assert actual == expected
