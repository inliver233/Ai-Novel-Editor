import ast
from pathlib import Path

import pytest


PRODUCTION_FILES = [
    "src/gui/dialogs/enhanced_find_dialog.py",
    "src/gui/dialogs/simple_find_dialog.py",
    "src/gui/dialogs/find_replace_dialog.py",
    "src/core/nlp_analyzer.py",
]


@pytest.mark.parametrize("relative_path", PRODUCTION_FILES)
def test_no_builtin_print_calls_in_production_files(relative_path: str) -> None:
    file_path = Path(__file__).resolve().parent.parent / relative_path
    source = file_path.read_text(encoding="utf-8")

    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError as exc:  # pragma: no cover
        pytest.fail(f"Failed to parse {relative_path}: {exc}")

    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "print":
            pytest.fail(f"Found print() in {relative_path}:{node.lineno}")
