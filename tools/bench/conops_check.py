#!/usr/bin/env python3
"""Validate config against CONOPS rules."""

from __future__ import annotations

import sys

from valiant.autonomy.conops import (
    task1_report_filename,
    task2_photo_filename,
    validate_conops_config,
)
from valiant.common.config import load_config


def main() -> int:
    print("=== CONOPS Config Check ===\n")

    vion = load_config("vion")
    vivi = load_config("vivi")

    season = vion.get("conops", {}).get("season", "unknown")
    print(f"CONOPS season: {season}")

    warnings = validate_conops_config(vion)
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"  WARN {warning}")
    else:
        print("  OK  runtime config matches conops.task2 limits")

    photo = task2_photo_filename(vion, 1)
    report = task1_report_filename(vivi)
    print(f"\nTask 2 photo example: {photo}")
    print(f"Task 1 report example: {report}")

    t2 = vion.get("conops", {}).get("task2", {})
    min_approach = vion.get("metric_recon", {}).get("min_approach_distance_m")
    print(f"\nMin approach distance: {min_approach} m (CONOPS: {t2.get('min_approach_distance_m')})")
    print(f"Shot confirmation: {t2.get('require_shot_confirmation')}")
    print(f"Max targets/window: {t2.get('max_targets_per_window')}")

    if warnings:
        print("\nFAILED - fix warnings above")
        return 1

    print("\nPASSED - CONOPS config ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
