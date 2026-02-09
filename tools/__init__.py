"""Repository tools (invoked via `python -m tools.<module>`).

Tools are executed from the repo root; ensure `src/` is on `sys.path` so
`import core...` works without requiring users to set PYTHONPATH manually.
"""

from __future__ import annotations

import sys
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC_PATH = _REPO_ROOT / "src"
if _SRC_PATH.exists() and str(_SRC_PATH) not in sys.path:
    sys.path.insert(0, str(_SRC_PATH))
