#!/usr/bin/env python3
"""Task 1 survey CLI — dry-run exercises timers + report offline."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="AEAC 2027 Task 1 wildlife survey runner")
    p.add_argument("--connection", default=None, help="MAVLink connection string (live)")
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="No MAVLink; exercise course timer, clustering, and report write",
    )
    p.add_argument(
        "--report",
        type=Path,
        default=Path("artifacts/survey_report.txt"),
        help="Submission report output path",
    )
    p.add_argument(
        "--ocr",
        action="store_true",
        help="Enable optional ear-tag OCR when a backend is installed",
    )
    return p


def run_dry(*, report: Path, ocr: bool) -> int:
    from valiant.missions.survey import SurveyRunner
    from valiant.perception.ocr import ocr_available, read_tag_text
    from valiant.perception.types import Detection

    runner = SurveyRunner()
    runner.start_course()
    runner.finish_course()

    # Synthetic fixes: two clusters (one with a tag).
    runner.record_fix(50.1000, -110.7400, tag="A1", id="d1")
    runner.record_fix(50.10001, -110.74001, id="d2")
    runner.record_fix(50.1010, -110.7410, id="d3")

    if ocr:
        det = Detection(cx=10, cy=10, label="ear_tag")
        # No real crop in dry-run — adapter returns empty text without backend.
        crop = None
        filled = read_tag_text(crop, det, enabled=True)
        print(f"OCR enabled={ocr} available={ocr_available()} text={filled.text!r}")

    out = runner.write_report(report)
    records = runner.build_report_records()
    print(f"Course time: {runner.course.elapsed_s():.2f} s")
    print(f"Clusters: {len(records)}")
    print(f"Wrote {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.dry_run or args.connection is None:
        if not args.dry_run and args.connection is None:
            print("No --connection; running --dry-run", file=sys.stderr)
        return run_dry(report=args.report, ocr=args.ocr)

    print(
        "Live MAVLink survey not wired in this thin CLI yet; use --dry-run",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
