"""Tests for SITL mission YAML loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from valiant.autonomy.sitl_mission import (
    SitlMissionError,
    apply_sitl_mission,
    load_sitl_mission,
    materialize_scenario,
)
from valiant.common.config import load_config, repo_root


def test_load_example_mission_file():
    path = repo_root() / "config" / "sitl_missions" / "example_wall.yaml"
    mission = load_sitl_mission(path)
    assert mission["name"] == "example_wall"
    assert mission["profile"] == "sitl"


def test_geofence_merges_into_sitl_block():
    cfg = load_config()
    mission = {
        "name": "t",
        "profile": "sitl",
        "scenario": "tests/fixtures/sitl_synthetic_multi.json",
        "geofence": {"max_north_m": 4.5, "max_east_m": 1.0},
    }
    merged, scenario, max_targets = apply_sitl_mission(cfg, mission)
    assert merged["sitl"]["max_north_m"] == 4.5
    assert merged["sitl"]["max_east_m"] == 1.0
    assert "sitl_synthetic_multi.json" in scenario
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


def test_sitl_physics_sets_camera_source():
    cfg = load_config()
    mission = {
        "name": "phys",
        "profile": "sitl_physics",
        "scenario": "tests/fixtures/sitl_physics_wall.json",
    }
    merged, _, _ = apply_sitl_mission(cfg, mission)
    assert merged["camera"]["source"] == "synthetic_physics"


def test_requires_scenario_or_world():
    with pytest.raises(SitlMissionError, match="scenario"):
        load_sitl_mission_from_dict({"name": "x", "profile": "sitl"})


def load_sitl_mission_from_dict(data: dict):
    path = repo_root() / "config" / "sitl_missions" / "_test_tmp.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    try:
        return load_sitl_mission(path)
    finally:
        path.unlink(missing_ok=True)
