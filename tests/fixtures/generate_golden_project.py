from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from .golden_project import create_golden_project


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the golden master project fixtures.")
    parser.add_argument(
        "output_dir",
        nargs="?",
        default="",
        help="Directory to create the project in (defaults to a temp directory).",
    )
    args = parser.parse_args()

    if args.output_dir:
        target_dir = Path(args.output_dir).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        base_dir = target_dir
    else:
        base_dir = Path(tempfile.mkdtemp(prefix="golden-project-"))

    result = create_golden_project(base_dir)
    print(str(result.project_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
