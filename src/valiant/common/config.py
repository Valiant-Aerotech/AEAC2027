"""Load per-drone YAML config with defaults merge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_DIR = _REPO_ROOT / "config"


def repo_root() -> Path:
    return _REPO_ROOT


def load_config(drone: str) -> dict[str, Any]:
    """Load config for a drone, merging defaults.yaml underneath.

    Parameters
    ----------
    drone:
        One of ``vion``, ``vivi``, ``vulcan2``.
    """
    defaults_path = _CONFIG_DIR / "defaults.yaml"
    drone_path = _CONFIG_DIR / f"{drone}.yaml"

    cfg: dict[str, Any] = {}
    if defaults_path.is_file():
        with open(defaults_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    if drone_path.is_file():
        with open(drone_path, encoding="utf-8") as f:
            drone_cfg = yaml.safe_load(f) or {}
        cfg = _deep_merge(cfg, drone_cfg)

    cfg["drone"] = drone
    return cfg


def _deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
