from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update repo-tracked golden fixtures (benchmark datasets, snapshots, etc.)."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Update all golden fixtures (explicit; overwrites existing fixtures).",
    )
    args = parser.parse_args(argv)

    if not args.all:
        raise SystemExit("No action specified. Use --help for available options.")

    repo_root = Path(__file__).resolve().parents[1]
    projects_root = repo_root / "tests" / "fixtures" / "projects"
    projects_root.mkdir(parents=True, exist_ok=True)

    sizes = ["small", "medium", "large"]
    for size in sizes:
        out_dir = projects_root / size
        if out_dir.exists():
            _safe_rmtree(out_dir, allowed_root=projects_root)
        _generate_project(size=size, out_dir=out_dir)
        print(f"[update_golden] generated: {out_dir}")

    return 0


def _safe_rmtree(path: Path, *, allowed_root: Path) -> None:
    resolved = path.resolve()
    allowed = allowed_root.resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise RuntimeError(f"Refusing to delete outside {allowed}: {resolved}") from exc
    shutil.rmtree(resolved, ignore_errors=True)


def _generate_project(*, size: str, out_dir: Path) -> None:
    from tools.generate_benchmark_project import generate_benchmark_project

    generate_benchmark_project(size=size, out_dir=out_dir)


if __name__ == "__main__":
    raise SystemExit(main())
