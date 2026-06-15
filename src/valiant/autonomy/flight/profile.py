"""Apply per-drone flight profile overlays to runtime config."""

from __future__ import annotations

from valiant.common.config import deep_merge


def apply_flight_profile(cfg: dict, profile: str | None) -> dict:
    """Merge ``flight_profiles.<profile>`` onto cfg when profile is set."""
    if not profile:
        return cfg
    profiles = cfg.get("flight_profiles", {})
    overlay = profiles.get(profile)
    if not overlay:
        print(f"[Profile] Unknown profile '{profile}' — using base config")
        return cfg
    merged = deep_merge(cfg, overlay)
    print(f"[Profile] Applied flight profile: {profile}")
    return merged


def mavlink_connection_for_host(cfg: dict) -> tuple[str, int]:
    """Pick MAVLink connection string and baud for onboard vs GCS host."""
    mavlink = cfg.get("mavlink", {})
    cam = cfg.get("camera", {})
    if cam.get("source") == "rpi_local":
        conn = mavlink.get("rpi_connection", "/dev/ttyAMA0")
    else:
        conn = mavlink.get("connection", "udpin:127.0.0.1:14550")
    baud = int(mavlink.get("baud", 57600))
    return conn, baud
