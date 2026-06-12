#!/usr/bin/env python3
"""Estimate rgb_to_depth scale/offset from calibration captures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from valiant.common.config import repo_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate RGB to depth pixel mapping")
    parser.add_argument("--scale-x", type=float, default=None)
    parser.add_argument("--scale-y", type=float, default=None)
    parser.add_argument("--offset-x", type=float, default=0.0)
    parser.add_argument("--offset-y", type=float, default=0.0)
    parser.add_argument("--depth-offset-m", type=float, default=0.0)
    parser.add_argument("--output", default="config/vion_calibration.yaml")
    args = parser.parse_args()

    out_path = repo_root() / args.output
    example = repo_root() / "config/vion_calibration.yaml.example"
    if out_path.is_file():
        with open(out_path, encoding="utf-8") as f:
            cal = yaml.safe_load(f) or {}
    elif example.is_file():
        with open(example, encoding="utf-8") as f:
            cal = yaml.safe_load(f) or {}
    else:
        cal = {}

    mapping = cal.setdefault("rgb_to_depth", {})
    if args.scale_x is not None:
        mapping["scale_x"] = args.scale_x
    if args.scale_y is not None:
        mapping["scale_y"] = args.scale_y
    mapping["offset_x"] = args.offset_x
    mapping["offset_y"] = args.offset_y
    cal["depth_offset_m"] = args.depth_offset_m

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.dump(cal, f, default_flow_style=False, sort_keys=False)

    print(f"Wrote {out_path}")
    print("Run tools/validate_calibration.py to check 10% gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
