"""Smoke tests: committed YAML and config merge load without error."""

from __future__ import annotations

import yaml

from valiant.autonomy.conops import validate_conops_config
from valiant.autonomy.sitl_mission import load_sitl_mission
from valiant.common.config import load_config, repo_root


def test_load_vion_and_rpas_config():
    vion = load_config("vion")
    rpas = load_config("rpas")
    assert vion.get("drone") == "vion"
    assert rpas.get("drone") == "rpas"
    assert "mavlink" in rpas
    assert "sitl" in rpas


def test_all_sitl_mission_yaml_files_parse():
    missions_dir = repo_root() / "config" / "sitl_missions"
    paths = sorted(missions_dir.glob("*.yaml"))
    assert paths, "expected at least one sitl_missions/*.yaml"
    for path in paths:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        assert isinstance(data, dict), f"{path.name} must be a YAML mapping"


def test_runnable_sitl_mission_files_load():
    """Full missions (name + scenario/world) pass load_sitl_mission; overlays are skipped."""
    missions_dir = repo_root() / "config" / "sitl_missions"
    loaded = 0
    for path in sorted(missions_dir.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not data.get("name"):
            continue
        if not (data.get("scenario") or data.get("world")):
            continue
        mission = load_sitl_mission(path)
        assert mission.get("name")
        assert mission.get("profile")
        loaded += 1
    assert loaded >= 1, "expected at least one runnable sitl_missions/*.yaml"


def test_validate_conops_config_returns_warnings_list():
    warnings = validate_conops_config(load_config("rpas"))
    assert isinstance(warnings, list)
