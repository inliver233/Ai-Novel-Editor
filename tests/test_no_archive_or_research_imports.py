import ast
from pathlib import Path

import pytest


_BANNED_TOP_LEVEL_MODULES = {"archive", "temp_research"}


def test_src_does_not_import_archive_or_temp_research() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    src_root = repo_root / "src"

    for file_path in src_root.rglob("*.py"):
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".", 1)[0]
                    if top_level in _BANNED_TOP_LEVEL_MODULES:
                        pytest.fail(
                            f"Disallowed import in {file_path}:{node.lineno}: import {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if not node.module:
                    continue
                top_level = node.module.split(".", 1)[0]
                if top_level in _BANNED_TOP_LEVEL_MODULES:
                    pytest.fail(
                        f"Disallowed import in {file_path}:{node.lineno}: from {node.module} import ..."
                    )
