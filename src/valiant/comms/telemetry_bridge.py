"""UDP telemetry mirror from Pi to GCS monitor (read-only)."""

from __future__ import annotations

import json
import socket
import time
from typing import Any


# Compact ids so the UDP payload stays small; the GCS monitor maps them back.
STATE_IDS = {
    "LAPS": 0,
    "TRANSIT": 1,
    "SWEEPING": 2,
    "IDENTIFYING": 3,
    "REPORTING": 4,
    "SEARCHING": 5,
    "APPROACHING": 6,
    "AIMING": 7,
    "ATTACHING": 8,
    "STANDOFF": 9,
    "TRACKING": 10,
    "COLLECTING": 11,
    "DELIVERING": 12,
    "RETREAT": 13,
    "RETURNING": 14,
    "COMPLETE": 15,
    "ABORTED": 16,
}


class TelemetryBridge:
    """Send lightweight JSON status to GCS over UDP."""

    def __init__(self, gcs_ip: str, port: int = 14560):
        self._addr = (gcs_ip, port)
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._last_send = 0.0
        self._min_interval_s = 0.2

    def send(
        self,
        *,
        state: str,
        distance_m: float | None = None,
        distance_min_m: float | None = None,
        distance_max_m: float | None = None,
        distance_source: str = "",
        depth_ok: bool = False,
        target_seen: bool = False,
        hand_test: bool = False,
        sitl: bool = False,
        vel_body: tuple[float, float, float] | None = None,
        gimbal_pwm: int | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        now = time.time()
        if now - self._last_send < self._min_interval_s:
            return
        self._last_send = now
        payload = {
            "ts": now,
            "state": state,
            "state_id": STATE_IDS.get(state, -1),
            "dist_m": distance_m,
            "dist_min_m": distance_min_m,
            "dist_max_m": distance_max_m,
            "distance_source": distance_source,
            "depth_ok": depth_ok,
            "target_seen": target_seen,
            "hand_test": hand_test,
            "sitl": sitl,
            "vel_x": vel_body[0] if vel_body else None,
            "vel_y": vel_body[1] if vel_body else None,
            "vel_z": vel_body[2] if vel_body else None,
            "gimbal_pwm": gimbal_pwm,
        }
        if extra:
            payload.update(extra)
        try:
            self._sock.sendto(json.dumps(payload).encode(), self._addr)
        except OSError as exc:
            print(f"[Telemetry] UDP send failed: {exc}")

    def close(self) -> None:
        self._sock.close()
