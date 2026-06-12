"""Pre-flight checks and warnings before hardware runs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from valiant.common.config import repo_root

if TYPE_CHECKING:
    from pymavlink import mavutil

_STATE_CODES = {
    "SEARCHING": 1.0,
    "APPROACHING": 2.0,
    "AIMING": 3.0,
    "FIRING": 4.0,
    "VERIFYING": 5.0,
    "CAPTURING": 6.0,
    "UPLOADING": 7.0,
    "COMPLETE": 8.0,
    "ABORTED": 9.0,
}


def state_code(state: str) -> float:
    return _STATE_CODES.get(state, 0.0)


def check_assets(cfg: dict[str, Any]) -> list[str]:
    """Return warning strings for missing onboard assets."""
    warnings: list[str] = []
    root = repo_root()

    cv = cfg.get("cv", {})
    if cv.get("method") in ("yolo", "both"):
        model = cv.get("models", {}).get("dry", "models/best.onnx")
        if not (root / model).is_file():
            warnings.append(f"YOLO model missing: {model} (run deploy_to_pi.ps1)")

    cal_file = cfg.get("calibration", {}).get("file")
    if cal_file and not (root / cal_file).is_file():
        warnings.append(
            f"Calibration missing: {cal_file} (copy from .example or calibrate)"
        )

    return warnings


def check_depth_mode(cfg: dict[str, Any], depth_available: bool) -> list[str]:
    """Warn when depth_at_target is configured but depth frames are unavailable."""
    mode = cfg.get("metric_recon", {}).get("rangefinder", "fov_estimate")
    if mode == "depth_at_target" and not depth_available:
        return [
            "depth_at_target configured but no ToF frames; using FOV fallback. "
            "2 m CONOPS gate may be inaccurate until ArduCam is wired."
        ]
    return []


def is_armed(master: mavutil.mavfile) -> bool | None:
    """Return armed state from last HEARTBEAT, or None if unknown."""
    hb = master.recv_match(type="HEARTBEAT", blocking=False)
    if hb is None:
        return None
    return bool(hb.base_mode & 128)  # MAV_MODE_FLAG_SAFETY_ARMED
