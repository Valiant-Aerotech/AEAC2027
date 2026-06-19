"""Load and apply SITL mission YAML overlays onto runtime config."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from valiant.common.config import deep_merge, repo_root


class SitlMissionError(ValueError):
    """Invalid or incomplete SITL mission file."""


def _resolve_path(path: str | Path, *, base: Path | None = None) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p.resolve()
    root = base or repo_root()
    return (root / p).resolve()


def load_sitl_mission(path: str | Path) -> dict[str, Any]:
    """Parse a SITL mission YAML file."""
    mission_path = _resolve_path(path)
    if not mission_path.is_file():
        raise SitlMissionError(f"Mission file not found: {mission_path}")
    with open(mission_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise SitlMissionError(f"Mission file must be a YAML mapping: {mission_path}")
    if not data.get("name"):
        raise SitlMissionError("Mission file requires 'name'")
    profile = data.get("profile", "sitl")
    if profile not in ("sitl", "sitl_physics"):
        raise SitlMissionError(f"Unknown profile {profile!r} (use sitl or sitl_physics)")
    if data.get("scenario") and data.get("world"):
        raise SitlMissionError("Use either 'scenario' or 'world', not both")
    if not data.get("scenario") and not data.get("world"):
        raise SitlMissionError("Mission needs 'scenario' path or inline 'world'")
    return data


def materialize_scenario(mission: dict[str, Any], out_dir: Path | None = None) -> Path:
    """Write generated scenario JSON from inline world (+ optional missions)."""
    world = mission.get("world")
    if not world:
        raise SitlMissionError("materialize_scenario requires mission['world']")
    name = str(mission.get("name", "mission"))
    out_root = out_dir or (repo_root() / "config" / "sitl_missions" / "generated")
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"{name}.json"

    profile = mission.get("profile", "sitl")
    if profile == "sitl_physics":
        payload: dict[str, Any] = dict(world)
        if "targets" in world:
            payload["targets"] = world["targets"]
    else:
        payload = {"world": dict(world)}
        if mission.get("missions"):
            payload["missions"] = mission["missions"]
        if mission.get("comment"):
            payload["comment"] = mission["comment"]

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return out_path


def _rel_scenario_path(path: Path) -> str:
    root = repo_root()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def apply_sitl_mission(cfg: dict[str, Any], mission: dict[str, Any]) -> tuple[dict[str, Any], str, int | None]:
    """Merge mission overlays; return (cfg, scenario_path, max_targets)."""
    merged = dict(cfg)
    geofence = mission.get("geofence") or {}
    if geofence:
        merged.setdefault("sitl", {})
        merged["sitl"] = deep_merge(merged["sitl"], geofence)

    for key in ("sitl", "auto_nav", "metric_recon", "gimbal", "camera", "safety"):
        block = mission.get(key)
        if block:
            merged[key] = deep_merge(merged.get(key, {}), block)

    profile = mission.get("profile", "sitl")
    if profile == "sitl_physics":
        merged.setdefault("camera", {})
        merged["camera"]["source"] = "synthetic_physics"
    elif mission.get("world") or mission.get("scenario"):
        merged.setdefault("camera", {})
        if merged["camera"].get("source") not in ("synthetic_physics",):
            merged["camera"]["source"] = "synthetic"

    if mission.get("scenario"):
        scenario_path = _resolve_path(mission["scenario"])
        if not scenario_path.is_file():
            raise SitlMissionError(f"Scenario file not found: {scenario_path}")
        scenario_rel = _rel_scenario_path(scenario_path)
    else:
        scenario_path = materialize_scenario(mission)
        scenario_rel = _rel_scenario_path(scenario_path)

    merged.setdefault("camera", {})
    merged["camera"]["synthetic_scenario"] = scenario_rel

    max_targets = mission.get("max_targets")
    if max_targets is not None:
        max_targets = int(max_targets)

    return merged, scenario_rel, max_targets


def apply_sitl_mission_from_file(cfg: dict[str, Any], path: str | Path) -> tuple[dict[str, Any], str, int | None]:
    """Load mission YAML and apply overlays."""
    mission = load_sitl_mission(path)
    return apply_sitl_mission(cfg, mission)
