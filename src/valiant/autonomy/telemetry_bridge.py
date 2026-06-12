"""MAVLink telemetry mirror from Pi to GCS (read-only monitor link)."""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING

from pymavlink import mavutil

if TYPE_CHECKING:
    from valiant.autonomy.packets import MetricPacket


class TelemetryBridge:
    """Send HEARTBEAT, STATUSTEXT, and NAMED_VALUE_FLOAT to GCS over UDP."""

    def __init__(self, cfg: dict):
        gcs_cfg = cfg.get("gcs_monitor", {})
        self.enabled = gcs_cfg.get("enabled", False)
        self.connection = gcs_cfg.get("connection", "udpout:127.0.0.1:14550")
        self.heartbeat_hz = gcs_cfg.get("heartbeat_hz", 1.0)
        self.ping_interval_s = gcs_cfg.get("ping_interval_s", 1.0)
        self._master: mavutil.mavfile | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._state = "INIT"
        self._last_metric: MetricPacket | None = None
        self._seq = 0

    def start(self) -> None:
        if not self.enabled:
            return
        try:
            self._master = mavutil.mavlink_connection(
                self.connection,
                source_system=1,
                source_component=191,
            )
        except Exception as exc:
            print(f"[TelemetryBridge] Could not open {self.connection}: {exc}")
            self.enabled = False
            return

        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[TelemetryBridge] Mirroring to {self.connection}")

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._master = None

    def update(self, state: str, metric: MetricPacket | None = None) -> None:
        self._state = state
        if metric is not None:
            self._last_metric = metric

    def send_statustext(self, message: str) -> None:
        if not self.enabled or self._master is None:
            return
        text = message[:50].encode()
        self._master.mav.statustext_send(mavutil.mavlink.MAV_SEVERITY_INFO, text)

    def _loop(self) -> None:
        assert self._master is not None
        last_heartbeat = 0.0
        last_ping = 0.0
        while not self._stop.is_set():
            now = time.time()
            if now - last_heartbeat >= 1.0 / self.heartbeat_hz:
                self._send_heartbeat()
                self._send_named_values()
                last_heartbeat = now
            if now - last_ping >= self.ping_interval_s:
                self._send_ping()
                last_ping = now
            time.sleep(0.05)

    def _send_heartbeat(self) -> None:
        assert self._master is not None
        self._master.mav.heartbeat_send(
            mavutil.mavlink.MAV_TYPE_ONBOARD_CONTROLLER,
            mavutil.mavlink.MAV_AUTOPILOT_INVALID,
            0,
            0,
            0,
        )

    def _send_ping(self) -> None:
        assert self._master is not None
        self._seq += 1
        self._master.mav.ping_send(
            int(time.time() * 1e6),
            self._seq,
            0,
            0,
        )

    def _send_named_values(self) -> None:
        assert self._master is not None
        self._send_named_float("state_id", float(hash(self._state) % 1000))
        metric = self._last_metric
        if metric and metric.distance_m is not None:
            self._send_named_float("dist_m", metric.distance_m)
        if metric and metric.distance_source:
            self._send_named_float("dist_src", float(hash(metric.distance_source) % 100))

    def _send_named_float(self, name: str, value: float) -> None:
        assert self._master is not None
        name_bytes = name.encode("ascii")[:10]
        name_bytes = name_bytes.ljust(10, b"\0")
        self._master.mav.named_value_float_send(
            int(time.time() * 1000) & 0xFFFFFFFF,
            name_bytes,
            value,
        )
