#!/usr/bin/env python3
"""Task 2 tagtrack CLI — dry-run exercises phases + track CSV offline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AEAC 2027 Task 2 tag-and-track runner")
    p.add_argument("--connection", default=None, help="MAVLink connection string (live)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="No MAVLink; walk attach→standoff→track→sample→deliver",
    )
    p.add_argument(
        "--log",
        type=Path,
        default=Path("artifacts/tagtrack_log.csv"),
        help="Appendix D track CSV output path",
    )
    return p


def run_dry(*, log: Path) -> int:
    from valiant.missions.tagtrack import TagTrackPhase, TagTrackRunner

    runner = TagTrackRunner(track_log_path=log, animal_id="A1")
    phase = runner.run_dry_sequence(animal_id="A1")
    print(f"Final phase: {phase.value}")
    print(f"Track samples logged: {runner._samples_logged}")
    if log.exists():
        print(f"Wrote {log}")
    if phase is not TagTrackPhase.COMPLETE:
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run or args.connection is None:
        if not args.dry_run and args.connection is None:
            print("No --connection; running --dry-run", file=sys.stderr)
        return run_dry(log=args.log)

    print(
        "Live MAVLink tagtrack not wired in this thin CLI yet; use --dry-run",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
