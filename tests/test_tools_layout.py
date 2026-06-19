"""Sanity check tools/ layout after reorganization."""

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
        "tools/run_sitl_mission.ps1",
        "tools/run_sitl_mission_file.ps1",
        "tools/run_sitl_pattern.ps1",
        "tools/run_sitl_orbit.ps1",
        "tools/sitl/sitl_orbit_flight.py",
        "tools/field/run_field_orbit.py",
        "tools/lib/wsl_distro.ps1",
        "tools/lib/guide_text.py",
        "tools/bench/verify_env.py",
        "tools/bench/diagnose.py",
        "tools/sitl/run_sitl_mission_file.py",
        "tools/dev/verify_ps1.ps1",
        "tools/dev/audit_script_paths.py",
        "config/sitl_missions/example_wall.yaml",
        "config/sitl_missions/pattern_box.yaml",
        "tools/gcs/verify_sitl_statustext.py",
    ],
)
def test_tools_layout_paths_exist(rel: str):
    assert (REPO / rel).is_file(), rel
