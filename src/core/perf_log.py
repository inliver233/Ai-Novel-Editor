from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_write_lock = threading.Lock()


def get_default_perf_log_path() -> Path:
    return Path.home() / ".ai-novel-editor" / "logs" / "perf.log"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def append_jsonl(record: Mapping[str, Any], *, path: Path | None = None) -> None:
    log_path = path or get_default_perf_log_path()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with _write_lock:
            with log_path.open("a", encoding="utf-8", newline="\n") as fp:
                fp.write(line)
                fp.write("\n")
    except Exception:
        logging.getLogger(__name__).exception("Failed to append perf jsonl: path=%s", log_path)


@dataclass(frozen=True, slots=True)
class PerfEvent:
    event: str
    fields: Mapping[str, Any]

    def to_record(self) -> dict[str, Any]:
        record: dict[str, Any] = {
            "ts": _utc_now_iso(),
            "pid": os.getpid(),
            "event": self.event,
        }
        record.update(self.fields)
        return record


def log_perf_event(event: str, /, **fields: Any) -> None:
    append_jsonl(PerfEvent(event=event, fields=fields).to_record())

