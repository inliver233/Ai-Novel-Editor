from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


FIXTURES_DIR = Path(__file__).resolve().parent
STORY_PATH = FIXTURES_DIR / "golden_story.txt"
TREE_PATH = FIXTURES_DIR / "golden_project_tree.json"


def load_golden_story() -> str:
    return STORY_PATH.read_text(encoding="utf-8")


def load_golden_tree() -> Dict[str, Any]:
    return json.loads(TREE_PATH.read_text(encoding="utf-8"))
