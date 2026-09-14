"""Runtime configuration: a plain YAML merge with no mission awareness.

Three layers, each optional except the first:

1. ``config/defaults.yaml``     - committed, the shared baseline
2. ``config/calibration.yaml``  - gitignored, per-airframe camera/depth calibration
3. ``config/local.yaml``        - gitignored, per-machine overrides (serial ports, paths)

An explicit path passed to :func:`load_config` is merged last, on top of all
three, which is what the ``--config`` flag on the CLI uses.

This module knows nothing about the competition. Mission rules live in the
mission packages that need them, as constants next to the code they govern.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CONFIG_DIR = _REPO_ROOT / "config"

DEFAULTS_FILE = "defaults.yaml"
CALIBRATION_FILE = "calibration.yaml"
LOCAL_FILE = "local.yaml"


def repo_root() -> Path:
    return _REPO_ROOT


def config_dir() -> Path:
    return _CONFIG_DIR


def defaults_path() -> Path:
    return _CONFIG_DIR / DEFAULTS_FILE


def calibration_path() -> Path:
    return _CONFIG_DIR / CALIBRATION_FILE


def local_path() -> Path:
    return _CONFIG_DIR / LOCAL_FILE


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config(config_path: str | Path | None = None) -> dict[str, Any]:
    """Merge the config layers and return the result.

    Parameters
    ----------
    config_path:
        Optional extra YAML merged last. Relative paths resolve against the
        repo root, so ``--config config/sitl_missions/survey.yaml`` works from
        anywhere.
    """
    cfg = _read_yaml(defaults_path())

    calibration = _read_yaml(calibration_path())
    if calibration:
        cfg["calibration"] = deep_merge(cfg.get("calibration", {}), calibration)

    cfg = deep_merge(cfg, _read_yaml(local_path()))

    if config_path is not None:
        extra = Path(config_path)
        if not extra.is_absolute() and not extra.is_file():
            extra = _REPO_ROOT / extra
        if not extra.is_file():
            raise FileNotFoundError(f"Config file not found: {config_path}")
        cfg = deep_merge(cfg, _read_yaml(extra))

    return cfg


def load_calibration() -> dict[str, Any]:
    """Per-airframe camera and depth calibration, empty when not yet captured."""
    return _read_yaml(calibration_path())


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
