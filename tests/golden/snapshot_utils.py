from __future__ import annotations

from pathlib import Path
import re


GOLDEN_DIR = Path(__file__).resolve().parent


UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
)
TS_RE = re.compile(
    r"\b\d{4}[-/]\d{2}[-/]\d{2}(?:[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)?\b"
)
WIN_PATH_RE = re.compile(r"[A-Za-z]:\\\\[^\s\"']+")
UNIX_PATH_RE = re.compile(
    r"/(?:Users|home|var|tmp|opt|etc|private|Volumes|mnt|srv|root)(?:/[^\s\"']+)?"
)
API_KEY_FIELD_RE = re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s,;]+)")
API_KEY_TOKEN_RE = re.compile(r"(?i)\bsk-[A-Za-z0-9]{10,}\b")


def _redact(content: str) -> str:
    text = API_KEY_FIELD_RE.sub(r"\1<API_KEY>", content)
    text = API_KEY_TOKEN_RE.sub("<API_KEY>", text)
    text = UUID_RE.sub("<UUID>", text)
    text = TS_RE.sub("<TIMESTAMP>", text)
    text = WIN_PATH_RE.sub("<ABS_PATH>", text)
    text = UNIX_PATH_RE.sub("<ABS_PATH>", text)
    return text


def _normalize(content: str) -> str:
    text = _redact(content.replace("\r\n", "\n")).rstrip()
    return f"{text}\n" if text else ""


def read_golden(name: str) -> str:
    return _normalize((GOLDEN_DIR / name).read_text(encoding="utf-8"))


def assert_golden(name: str, content: str) -> None:
    expected = read_golden(name)
    actual = _normalize(content)
    assert actual == expected
