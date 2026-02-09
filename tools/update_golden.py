from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Update repo-tracked golden fixtures (benchmark datasets, snapshots, etc.)."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Update all golden fixtures (explicit; will be implemented in ANE-0255).",
    )
    args = parser.parse_args(argv)

    if args.all:
        raise SystemExit("tools.update_golden --all is not implemented yet (see ANE-0255).")

    raise SystemExit("No action specified. Use --help for available options.")


if __name__ == "__main__":
    raise SystemExit(main())

