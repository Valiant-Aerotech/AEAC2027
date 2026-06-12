"""ArduCopter flight mode management for indoor/outdoor profiles."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymavlink import mavutil

GUIDED = 4
GUIDED_NOGPS = 20

_PROFILE_MODES = {
    "outdoor": GUIDED,
    "indoor": GUIDED_NOGPS,
}


class FlightModeManager:
    """Select and monitor GUIDED vs GUIDED_NOGPS based on flight profile."""

    def __init__(self, master: mavutil.mavfile, cfg: dict, *, sim: bool = False):
        self.master = master
        self.sim = sim
        flight = cfg.get("flight", {})
        self.profile = flight.get("profile", "outdoor")
        self.require_gps = flight.get("require_gps", self.profile != "indoor")
        self.target_mode_id = _PROFILE_MODES.get(self.profile, GUIDED)
        explicit_mode = flight.get("mode", "").upper()
        if explicit_mode == "GUIDED_NOGPS":
            self.target_mode_id = GUIDED_NOGPS
        elif explicit_mode == "GUIDED":
            self.target_mode_id = GUIDED
        self._last_mode_check = 0.0
        self._rc_override = False

    @property
    def target_mode_name(self) -> str:
        return "GUIDED_NOGPS" if self.target_mode_id == GUIDED_NOGPS else "GUIDED"

    def ensure_mode(self) -> None:
        """Request target flight mode if not in sim."""
        if self.sim:
            return
        now = time.time()
        if now - self._last_mode_check < 2.0:
            return
        self._last_mode_check = now

        heartbeat = self.master.recv_match(type="HEARTBEAT", blocking=False)
        if heartbeat is None:
            return
        current_mode = heartbeat.custom_mode
        if current_mode == self.target_mode_id:
            return

        self.master.mav.set_mode_send(
            self.master.target_system,
            1,  # MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
            self.target_mode_id,
        )

    def check_rc_override(self) -> bool:
        """Return True if FC mode is no longer the autonomous target mode."""
        if self.sim:
            return False
        heartbeat = self.master.recv_match(type="HEARTBEAT", blocking=False)
        if heartbeat is None:
            return False
        current_mode = heartbeat.custom_mode
        if current_mode not in (GUIDED, GUIDED_NOGPS):
            self._rc_override = True
            return True
        if current_mode != self.target_mode_id:
            return True
        return False

    def arm_check_message(self) -> str | None:
        if self.require_gps:
            return None
        return "GPS not required for indoor profile"
