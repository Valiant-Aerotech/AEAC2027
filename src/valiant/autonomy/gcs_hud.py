"""Rate-limited MAVLink STATUSTEXT for Mission Planner / GCS HUD."""

from __future__ import annotations

import time

from pymavlink import mavutil

from valiant.common.mavlink import send_statustext

HUD_PREFIX = "T2: "
MAX_STATUSTEXT_LEN = 50


class GcsHudReporter:
    """Send companion STATUSTEXT (max 50 chars) without flooding the GCS."""

    def __init__(
        self,
        master: mavutil.mavfile,
        *,
        prefix: str = HUD_PREFIX,
        interval_s: float = 3.0,
    ):
        self._master = master
        self._prefix = prefix
        self._interval_s = max(0.5, interval_s)
        self._last_sent = 0.0
        self._last_body = ""

    def send(self, message: str, *, force: bool = False) -> None:
        body = message.strip()
        if not body:
            return
        max_body = MAX_STATUSTEXT_LEN - len(self._prefix.encode("utf-8", errors="ignore"))
        body = body[:max_body]
        now = time.time()
        if not force:
            if body == self._last_body:
                return
            if now - self._last_sent < self._interval_s:
                return
        send_statustext(self._master, body, prefix=self._prefix)
        self._last_body = body
        self._last_sent = now


def format_sitl_status_line(
    *,
    state: str,
    target_seen: bool,
    metric_range_m: float | None = None,
    wall_range_m: float | None = None,
    pose_n: float | None = None,
    pose_e: float | None = None,
    alt_m: float | None = None,
    vel_n: float | None = None,
    motion_rule: str = "",
    motion_reason: str = "",
    fire_blockers: tuple[str, ...] = (),
) -> str:
    """Compact mission status for STATUSTEXT (body only, no prefix)."""
    parts: list[str] = [state[:8]]
    if pose_n is not None and pose_e is not None:
        parts.append(f"N{pose_n:.0f}E{pose_e:.0f}")
    if alt_m is not None:
        parts.append(f"z{alt_m:.0f}m")
    parts.append("tgt" if target_seen else "scan")
    if metric_range_m is not None:
        parts.append(f"rng{metric_range_m:.1f}m")
    if wall_range_m is not None:
        parts.append(f"wall{wall_range_m:.1f}m")
    if motion_rule:
        parts.append(motion_rule[:6])
    elif vel_n is not None and abs(vel_n) > 0.04:
        parts.append(f"vn{vel_n:+.2f}")
    if fire_blockers:
        parts.append("blk:" + ",".join(fire_blockers[:2])[:12])
    elif motion_reason:
        parts.append(motion_reason[:14])
    line = " ".join(parts)
    return line[: MAX_STATUSTEXT_LEN - len(HUD_PREFIX.encode())]
