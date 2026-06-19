"""Pilot override and kill-switch detection for GUIDED companion scripts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pymavlink import mavutil

from valiant.autonomy.sitl_preflight import _flight_mode_from_heartbeat
from valiant.common.mavlink_io import mavlink_io

EMERGENCY_MODES = frozenset({"LAND", "RTL", "BRAKE", "QRTL", "QLAND", "AUTO_RTL"})


class OverrideKind(str, Enum):
    NONE = "none"
    MANUAL_TAKEOVER = "manual"
    EMERGENCY = "emergency"
    KILL_SWITCH = "kill"
    DISARMED = "disarmed"


@dataclass(frozen=True)
class PilotSnapshot:
    mode: str
    armed: bool
    kill_active: bool


def _pilot_cfg(cfg: dict) -> dict:
    return cfg.get("field_orbit", {}).get("pilot", {})


class PilotOverrideMonitor:
    """Poll HEARTBEAT and RC_CHANNELS for pilot override / kill switch."""

    def __init__(self, master: mavutil.mavfile, cfg: dict):
        self._master = master
        pilot = _pilot_cfg(cfg)
        self._kill_channel = pilot.get("kill_switch_rc_channel")
        self._kill_pwm_high = float(pilot.get("kill_switch_pwm_high", 1300))
        self._snapshot = PilotSnapshot(mode="UNKNOWN", armed=False, kill_active=False)

    @property
    def snapshot(self) -> PilotSnapshot:
        return self._snapshot

    def sync_from_vehicle(self, *, timeout_s: float = 3.0) -> bool:
        """Refresh armed/mode from one FC HEARTBEAT (call after arm/preflight)."""
        import time

        target_sys = getattr(self._master, "target_system", 0)
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            with mavlink_io(self._master):
                msg = self._master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.5)
            if msg is None or msg.get_srcSystem() != target_sys:
                continue
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            mode = _flight_mode_from_heartbeat(self._master, msg)
            self._snapshot = PilotSnapshot(mode=mode, armed=armed, kill_active=False)
            return True
        return False

    def poll(self) -> OverrideKind:
        mode = self._master.flightmode or self._snapshot.mode or "UNKNOWN"
        armed = self._snapshot.armed
        kill_active = False
        target_sys = getattr(self._master, "target_system", 0)

        with mavlink_io(self._master):
            while True:
                msg = self._master.recv_match(
                    type=["HEARTBEAT", "RC_CHANNELS"],
                    blocking=False,
                )
                if msg is None:
                    break
                if msg.get_srcSystem() != target_sys:
                    continue
                if msg.get_type() == "HEARTBEAT":
                    armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
                    mode = _flight_mode_from_heartbeat(self._master, msg)
                elif msg.get_type() == "RC_CHANNELS" and self._kill_channel is not None:
                    ch = int(self._kill_channel)
                    pwm = _rc_channel_pwm(msg, ch)
                    if pwm is not None and pwm > self._kill_pwm_high:
                        kill_active = True

        self._snapshot = PilotSnapshot(mode=mode, armed=armed, kill_active=kill_active)

        if kill_active:
            return OverrideKind.KILL_SWITCH
        if not armed:
            return OverrideKind.DISARMED
        if mode in EMERGENCY_MODES:
            return OverrideKind.EMERGENCY
        if mode != "GUIDED":
            return OverrideKind.MANUAL_TAKEOVER
        return OverrideKind.NONE


def _rc_channel_pwm(msg, channel: int) -> int | None:
    """Return PWM for 1-based RC channel from RC_CHANNELS message."""
    if channel < 1 or channel > 18:
        return None
    field = f"chan{channel}_raw"
    if not hasattr(msg, field):
        return None
    raw = int(getattr(msg, field))
    if raw <= 0:
        return None
    return raw


def override_message(kind: OverrideKind) -> str:
    if kind == OverrideKind.KILL_SWITCH:
        return "Emergency stop - companion stopped"
    if kind == OverrideKind.EMERGENCY:
        return "Emergency stop - companion stopped"
    if kind == OverrideKind.MANUAL_TAKEOVER:
        return "Pilot takeover - companion stopped"
    if kind == OverrideKind.DISARMED:
        return "Disarmed - companion stopped"
    return ""
