"""Per-loop safety checks - battery, geofence, mission timeout."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymavlink import mavutil


@dataclass(frozen=True)
class SafetyAbort:
    """Reason the mission must stop."""

    reason: str
    trigger_rtl: bool = False


class SafetyMonitor:
    """Poll MAVLink and elapsed time for abort conditions."""

    _GEOFENCE_KEYWORDS = ("geofence", "fence breach", "fence breached")

    def __init__(self, master: mavutil.mavfile | None, cfg: dict, *, sim: bool = False):
        self.master = master
        self.cfg = cfg.get("safety", {})
        self.sim = sim
        self.min_battery_pct = self.cfg.get("min_battery_pct", 20)
        self.check_battery = self.cfg.get("check_battery", True)
        self.geofence_abort = self.cfg.get("geofence_abort", True)
        self.mission_timeout_s = self.cfg.get("mission_timeout_s", 600)
        self.rtl_on_abort = self.cfg.get("rtl_on_abort", False)
        self._battery_pct: int | None = None
        self._geofence_breached = False
        self._mission_start = time.time()

    @property
    def battery_pct(self) -> int | None:
        return self._battery_pct

    def _drain_mavlink(self) -> None:
        if self.sim or self.master is None:
            return

        from valiant.common.mavlink_io import mavlink_io

        with mavlink_io(self.master):
            while True:
                msg = self.master.recv_match(
                    type=["SYS_STATUS", "FENCE_STATUS", "STATUSTEXT"],
                    blocking=False,
                )
                if msg is None:
                    break
                msg_type = msg.get_type()
                if msg_type == "SYS_STATUS":
                    remaining = getattr(msg, "battery_remaining", -1)
                    if remaining >= 0:
                        self._battery_pct = int(remaining)
                elif msg_type == "FENCE_STATUS" and self.geofence_abort:
                    breach_status = getattr(msg, "breach_status", 0)
                    if breach_status != 0:
                        self._geofence_breached = True
                elif msg_type == "STATUSTEXT" and self.geofence_abort:
                    text = getattr(msg, "text", "")
                    if isinstance(text, bytes):
                        text = text.decode(errors="ignore")
                    lowered = text.lower()
                    if any(keyword in lowered for keyword in self._GEOFENCE_KEYWORDS):
                        self._geofence_breached = True

    def check(self) -> SafetyAbort | None:
        """Return an abort reason or None if safe to continue."""
        self._drain_mavlink()

        elapsed = time.time() - self._mission_start
        if self.mission_timeout_s > 0 and elapsed > self.mission_timeout_s:
            return SafetyAbort(
                f"mission timeout ({int(elapsed)}s)",
                trigger_rtl=self.rtl_on_abort,
            )

        if not self.sim and self._geofence_breached:
            return SafetyAbort("geofence breach", trigger_rtl=self.rtl_on_abort)

        if (
            self.check_battery
            and not self.sim
            and self._battery_pct is not None
            and self._battery_pct < self.min_battery_pct
        ):
            return SafetyAbort(
                f"battery {self._battery_pct}% < {self.min_battery_pct}%",
                trigger_rtl=self.rtl_on_abort,
            )

        return None
