from __future__ import annotations

import os
import sys


def _try_force_utf8(stream) -> None:
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        return


_try_force_utf8(sys.stdout)
_try_force_utf8(sys.stderr)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")

for path in [PROJECT_ROOT, SRC_ROOT]:
    if path not in sys.path:
        sys.path.insert(0, path)
