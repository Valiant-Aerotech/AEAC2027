"""Tests for SITL mission YAML loader (inline world / scenario fixtures)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from valiant.core.config import load_config, repo_root
from valiant.sim.mission import (
    SitlMissionError,
    apply_sitl_mission,
    load_sitl_mission,
    materialize_scenario,
)


def test_load_orbit_overlay_is_not_a_scenario_mission():
    """orbit.yaml is a field_orbit overlay, not a sitl mission scenario file."""
    path = repo_root() / "config" / "sitl_missions" / "orbit.yaml"
    with pytest.raises(SitlMissionError, match="name|scenario"):
        load_sitl_mission(path)


def test_geofence_merges_into_sitl_block():
    cfg = load_config()
    mission = {
        "name": "t",
        "profile": "sitl",
        "scenario": "tests/fixtures/sitl_survey_world.json",
        "geofence": {"max_north_m": 4.5, "max_east_m": 1.0},
    }
    merged, scenario, max_targets = apply_sitl_mission(cfg, mission)
    assert merged["sitl"]["max_north_m"] == 4.5
    assert merged["sitl"]["max_east_m"] == 1.0
    assert "sitl_survey_world.json" in scenario
    assert max_targets is None


def test_inline_world_materializes_json(tmp_path: Path):
    mission = {
        "name": "inline_test",
        "profile": "sitl",
        "world": {
            "wall": {"x_m": 4.0, "y_min": -2.0, "y_max": 2.0, "z_top": -2.0, "z_base": 0.0},
            "targets": [
                {
                    "id": "t1",
                    "position_ned": [4.0, 0.0, -1.0],
                    "diameter_m": 0.2,
                    "color": [180, 50, 180],
                }
            ],
        },
    }
    out = materialize_scenario(mission, out_dir=tmp_path)
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "world" in data
    assert data["world"]["wall"]["x_m"] == 4.0


def test_survey_fixture_as_scenario():
    cfg = load_config()
    mission = {
        "name": "survey",
        "profile": "sitl",
        "scenario": "tests/fixtures/sitl_survey_world.json",
    }
    merged, scenario, _ = apply_sitl_mission(cfg, mission)
    assert "sitl_survey_world.json" in scenario
    assert merged["camera"]["source"] == "synthetic"


def test_requires_scenario_or_world(tmp_path: Path):
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump({"name": "x", "profile": "sitl"}), encoding="utf-8")
    with pytest.raises(SitlMissionError, match="scenario"):
        load_sitl_mission(path)
