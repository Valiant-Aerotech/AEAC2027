#!/usr/bin/env python3
"""Run a SITL mission from a YAML config file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from valiant.autonomy.orchestrator import run_auto_extinguish  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run SITL mission from YAML config")
    parser.add_argument("mission_file", help="Path to config/sitl_missions/*.yaml")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--skip-sitl-preflight", action="store_true")
    args = parser.parse_args()
    run_auto_extinguish(
        sitl=True,
        headless=args.headless,
        mission_file=args.mission_file,
        skip_sitl_preflight=args.skip_sitl_preflight,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
