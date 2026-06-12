"""Flight profile presets for Vion (indoor/outdoor, Pi companion)."""

from __future__ import annotations

from typing import Any


def apply_vion_profile(
    cfg: dict[str, Any],
    profile: str,
    *,
    source: str | None = None,
    gcs_ip: str | None = None,
    enable_gcs_monitor: bool | None = None,
) -> dict[str, Any]:
    """Apply flight/camera/metric presets for onboard or bench runs.

    Mutates and returns cfg. Centralizes logic used by run_mission.py and orchestrator.
    """
    flight = cfg.setdefault("flight", {})
    flight["profile"] = profile

    if source:
        cfg.setdefault("camera", {})["source"] = source

    if profile == "indoor":
        flight["require_gps"] = False
        flight["mode"] = "GUIDED_NOGPS"
        flight["arm_check_gps"] = False
        cfg.setdefault("safety", {})["geofence_abort"] = False

    if source == "rpi_local":
        cfg.setdefault("metric_recon", {})["rangefinder"] = "depth_at_target"
        monitor = enable_gcs_monitor if enable_gcs_monitor is not None else True
        gcs = cfg.setdefault("gcs_monitor", {})
        gcs["enabled"] = monitor
        if gcs_ip:
            gcs["connection"] = f"udpout:{gcs_ip}:14550"

    return cfg


def gcs_monitor_connection(cfg: dict[str, Any], gcs_ip: str | None = None) -> str | None:
    """Build UDP monitor target; returns None if monitor disabled."""
    gcs = cfg.get("gcs_monitor", {})
    if not gcs.get("enabled", False):
        return None
    if gcs_ip:
        return f"udpout:{gcs_ip}:14550"
    return gcs.get("connection")
