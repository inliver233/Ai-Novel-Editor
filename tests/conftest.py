from __future__ import annotations

import sys
from pathlib import Path


def _try_force_utf8(stream) -> None:
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        return


_try_force_utf8(sys.stdout)
_try_force_utf8(sys.stderr)

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

