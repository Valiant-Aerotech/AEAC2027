"""Sanity check tools/ layout after 2027 cleanup."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "rel",
    [
        "tools/valiant.py",
        "tools/setup.ps1",
        "tools/setup_wsl.ps1",
        "tools/launch_sitl.ps1",
        "tools/run_sitl_pattern.ps1",
        "tools/run_sitl_orbit.ps1",
        "tools/sitl/sitl_orbit_flight.py",
        "tools/sitl/sitl_pattern_flight.py",
        "tools/sitl/launch_sitl.sh",
        "tools/field/run_field_orbit.py",
        "tools/lib/guide_text.py",
        "tools/bench/verify_env.py",
        "tools/bench/diagnose.py",
        "tools/bench/safety_bench_test.py",
        "tools/calibrate/calibrate_depth_rgb.py",
        "tools/dev/audit_script_paths.py",
        "config/sitl_missions/orbit.yaml",
        "config/sitl_missions/pattern_box.yaml",
        "config/aeac2027_boundary.poly",
        "config/defaults.yaml",
        "src/valiant/missions/survey/course.py",
        "src/valiant/missions/survey/runner.py",
        "src/valiant/missions/tagtrack/__init__.py",
        "src/valiant/missions/tagtrack/runner.py",
        "src/valiant/perception/ocr.py",
        "tools/survey/run_survey.py",
        "tools/tagtrack/run_tagtrack.py",
        "tools/gcs/verify_sitl_statustext.py",
        "hardware/vion/lua/safety.lua",
        "docs/conops-2027.md",
        "reference/topics.md",
    ],
)
def test_tools_layout_paths_exist(rel: str):
    assert (REPO / rel).is_file(), rel


@pytest.mark.parametrize(
    "rel",
    [
        "tools/run_sitl_mission.ps1",
        "tools/run_sitl_mission_file.ps1",
        "tools/sitl/run_sitl_mission_file.py",
        "tools/bench/cv_bench_test.py",
        "tools/bench/metric_bench_test.py",
        "hardware/vion/rpi/run_mission.py",
        "config/rpas.yaml",
        "src/valiant/autonomy/orchestrator.py",
    ],
)
def test_2026_ghosts_are_gone(rel: str):
    assert not (REPO / rel).exists(), f"stale 2026 path still present: {rel}"
