"""coinfodesign build --source <dir|omit for pinned fetch> --out _site [--commit SHA]"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .build import build, resolve_commit
from .data import EvidenceError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="coinfodesign")
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build", help="verify source losses and build the static site")
    build_parser.add_argument(
        "--source", type=Path, default=None,
        help="local directory with full_loss_table_real_to_real.csv and subset_metadata_table.csv "
             "(default: fetch from the pinned immutable upstream commit)",
    )
    build_parser.add_argument("--out", type=Path, default=Path("_site"))
    build_parser.add_argument("--commit", type=str, default=None, help="build identifier shown in the site")

    args = parser.parse_args(argv)
    if args.command == "build":
        commit = resolve_commit(args.commit)
        try:
            payload = build(args.source, args.out, commit)
        except EvidenceError as exc:
            print(f"EVIDENCE ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"Built {payload['case_count']} cases -> {args.out} (build {commit})")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
