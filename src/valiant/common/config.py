"""Load per-drone YAML config with defaults merge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from valiant.autonomy.conops import apply_conops_to_runtime

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_DIR = _REPO_ROOT / "config"

# Default platform id (Remotely Piloted Aircraft System).
DEFAULT_DRONE = "rpas"

# Platform config may inherit airframe tuning from another YAML file.
_CONFIG_BASE: dict[str, str] = {"rpas": "vion", "vivi": "vion"}


def repo_root() -> Path:
    return _REPO_ROOT


def config_dir() -> Path:
    return _CONFIG_DIR


def default_config_name() -> str:
    return DEFAULT_DRONE


def default_config_path() -> Path:
    return _CONFIG_DIR / f"{DEFAULT_DRONE}.yaml"


def default_calibration_path() -> Path:
    return _CONFIG_DIR / f"{DEFAULT_DRONE}_calibration.yaml"


def default_calibration_example_path() -> Path:
    return _CONFIG_DIR / f"{DEFAULT_DRONE}_calibration.yaml.example"


def load_default_config() -> dict[str, Any]:
    """Load the default RPAS platform config."""
    return load_config(DEFAULT_DRONE)


def _calibration_paths(drone: str) -> list[Path]:
    """Calibration YAML files to merge, in order (base airframe then platform)."""
    seen: set[Path] = set()
    paths: list[Path] = []
    for layer in _config_layers(drone):
        path = _CONFIG_DIR / f"{layer}_calibration.yaml"
        if path not in seen:
            seen.add(path)
            paths.append(path)
    legacy = _CONFIG_DIR / "vion_calibration.yaml"
    if legacy not in seen:
        paths.append(legacy)
    return paths


def load_calibration(drone: str | None = None) -> dict[str, Any]:
    """Load per-airframe calibration YAML (rgb/depth alignment, FOV, validation)."""
    drone = drone or DEFAULT_DRONE
    cal: dict[str, Any] = {}
    for path in _calibration_paths(drone):
        if path.is_file():
            with open(path, encoding="utf-8") as f:
                cal = deep_merge(cal, yaml.safe_load(f) or {})
    return cal


def _config_layers(drone: str) -> list[str]:
    base = _CONFIG_BASE.get(drone)
    if base and base != drone:
        return [base, drone]
    return [drone]


def load_config(drone: str | None = None) -> dict[str, Any]:
    """Load config for a drone, merging defaults.yaml underneath.

    Parameters
    ----------
    drone:
        Platform or airframe id (default ``rpas``). ``rpas`` and ``vivi`` inherit
        ``vion.yaml`` then apply their platform YAML. ``vion`` loads ``vion.yaml`` only.
    """
    drone = drone or DEFAULT_DRONE
    defaults_path = _CONFIG_DIR / "defaults.yaml"
    conops_path = _CONFIG_DIR / "conops.yaml"

    cfg: dict[str, Any] = {}
    if defaults_path.is_file():
        with open(defaults_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    if conops_path.is_file():
        with open(conops_path, encoding="utf-8") as f:
            conops_cfg = yaml.safe_load(f) or {}
        cfg = deep_merge(cfg, conops_cfg)

    for layer in _config_layers(drone):
        drone_path = _CONFIG_DIR / f"{layer}.yaml"
        if drone_path.is_file():
            with open(drone_path, encoding="utf-8") as f:
                drone_cfg = yaml.safe_load(f) or {}
            cfg = deep_merge(cfg, drone_cfg)

    cal = load_calibration(drone)
    if cal:
        cfg["calibration"] = deep_merge(cfg.get("calibration", {}), cal)

    cfg["drone"] = drone
    return apply_conops_to_runtime(cfg)


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
