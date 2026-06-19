"""Guided SITL pattern flight: straight legs, turns, then LOITER."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass

from pymavlink import mavutil

from valiant.autonomy.auto_nav.mavlink_stream import VelocityStream
from valiant.autonomy.auto_nav.visual_servo import VisualServo
from valiant.autonomy.gcs_hud import GcsHudReporter
from valiant.common.mavlink import (
    connect,
    gcs_statustext_options_from_cfg,
    request_sitl_telemetry_streams,
    send_companion_heartbeat,
)
from valiant.common.sitl_physics import drain_vehicle_pose


def _wrap_pi(angle: float) -> float:
    while angle > math.pi:
        angle -= 2 * math.pi
    while angle < -math.pi:
        angle += 2 * math.pi
    return angle


@dataclass(frozen=True)
class PatternLeg:
    kind: str
    value: float
    label: str


DEFAULT_PATTERN: tuple[PatternLeg, ...] = (
    PatternLeg("forward", 10.0, "Flying forward 10 m"),
    PatternLeg("turn", 90.0, "Turning right 90 deg"),
    PatternLeg("forward", 5.0, "Flying forward 5 m"),
    PatternLeg("turn", -180.0, "Turning left 180 deg"),
    PatternLeg("forward", 5.0, "Flying forward 5 m"),
    PatternLeg("turn", -90.0, "Turning left 90 deg"),
    PatternLeg("forward", 10.0, "Flying forward 10 m"),
)


class SitlPatternRunner:
    """Execute a scripted GUIDED box pattern, then switch to LOITER."""

    def __init__(
        self,
        master: mavutil.mavfile,
        cfg: dict,
        *,
        hud: GcsHudReporter | None = None,
        speed_m_s: float = 0.45,
        yaw_rate_rad_s: float = 0.35,
    ):
        self.master = master
        self.cfg = cfg
        self._hud = hud
        self._speed = max(0.1, speed_m_s)
        self._yaw_rate = max(0.1, yaw_rate_rad_s)
        self._servo = VisualServo(master, cfg)
        self._stream = VelocityStream(self._servo, rate_hz=20.0)
        self._last_hb = 0.0

    def _say(self, message: str, *, force: bool = True) -> None:
        print(f"[Pattern] {message}")
        if self._hud is not None:
            self._hud.send(message, force=force)

    def _heartbeat(self) -> None:
        now = time.time()
        if now - self._last_hb > 1.0:
            send_companion_heartbeat(self.master)
            self._last_hb = now

    def _pose(self, previous=None):
        self._heartbeat()
        pose = drain_vehicle_pose(self.master, previous)
        if pose.ok:
            self._servo.set_yaw_rad(pose.yaw)
        return pose

    def _stop(self) -> None:
        self._stream.stop()
        self._servo.stop()

    def _drive_forward(self, distance_m: float, *, label: str) -> None:
        self._say(label)
        self._stream.start()
        pose = self._pose()
        if not pose.ok:
            raise RuntimeError("No LOCAL_POSITION_NED for pattern flight")
        x0, y0 = pose.x, pose.y
        deadline = time.time() + max(30.0, distance_m / self._speed * 3.0)
        while time.time() < deadline:
            pose = self._pose(pose)
            traveled = math.hypot(pose.x - x0, pose.y - y0)
            if traveled >= distance_m:
                break
            self._servo.send_velocity_body(self._speed, 0.0, 0.0)
            time.sleep(0.05)
        self._stop()
        time.sleep(0.3)

    def _turn_degrees(self, degrees: float, *, label: str) -> None:
        self._say(label)
        self._stream.start()
        pose = self._pose()
        if not pose.ok:
            raise RuntimeError("No attitude for pattern turn")
        target_delta = math.radians(degrees)
        yaw0 = pose.yaw
        rate = self._yaw_rate if degrees >= 0 else -self._yaw_rate
        deadline = time.time() + max(20.0, abs(target_delta) / self._yaw_rate * 2.5)
        while time.time() < deadline:
            pose = self._pose(pose)
            delta = _wrap_pi(pose.yaw - yaw0)
            if degrees >= 0 and delta >= target_delta - math.radians(2.0):
                break
            if degrees < 0 and delta <= target_delta + math.radians(2.0):
                break
            self._servo.send_yaw_rate(rate)
            time.sleep(0.05)
        self._stop()
        time.sleep(0.3)

    def _set_loiter(self) -> None:
        mapping = self.master.mode_mapping()
        if "LOITER" not in mapping:
            raise RuntimeError(f"LOITER not available: {mapping}")
        self._say("Loiter - manual control")
        self.master.set_mode(mapping["LOITER"])
        deadline = time.time() + 8.0
        want = mapping["LOITER"]
        while time.time() < deadline:
            self._heartbeat()
            hb = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=1.0)
            if hb is not None and hb.get_srcSystem() == self.master.target_system:
                if hb.custom_mode == want:
                    return
        print("[Pattern] Warning: LOITER not confirmed")

    def run(self, legs: tuple[PatternLeg, ...] | None = None) -> None:
        legs = legs or DEFAULT_PATTERN
        self._say("Pattern flight starting")
        request_sitl_telemetry_streams(self.master)
        for leg in legs:
            if leg.kind == "forward":
                self._drive_forward(leg.value, label=leg.label)
            elif leg.kind == "turn":
                self._turn_degrees(leg.value, label=leg.label)
            else:
                raise ValueError(f"Unknown leg kind: {leg.kind}")
        self._set_loiter()
        self._say("Pattern complete - hold in loiter")


def run_pattern_flight(
    *,
    connection: str,
    cfg: dict,
    takeoff_alt_m: float = 5.0,
    skip_preflight: bool = False,
    speed_m_s: float = 0.45,
) -> None:
    """Connect, take off in GUIDED, fly the default box, end in LOITER."""
    from valiant.autonomy.sitl_preflight import arm_guided_takeoff

    master = connect(connection, cfg.get("mavlink", {}).get("baud", 57600))
    gcs_cfg = cfg.get("gcs_monitor", {})
    hud = GcsHudReporter(
        master,
        interval_s=float(gcs_cfg.get("statustext_interval_s", 3.0)),
        options=gcs_statustext_options_from_cfg(cfg, sitl=True),
    )
    try:
        if skip_preflight:
            print("[Pattern] Skipping preflight (assume armed + GUIDED + airborne)")
        else:
            arm_guided_takeoff(
                master,
                takeoff_alt_m=takeoff_alt_m,
                timeout_s=float(cfg.get("sitl", {}).get("preflight_timeout_s", 75.0)),
                ekf_wait_s=float(cfg.get("sitl", {}).get("ekf_wait_s", 45.0)),
            )
        runner = SitlPatternRunner(master, cfg, hud=hud, speed_m_s=speed_m_s)
        runner.run()
    finally:
        hud.close()
        try:
            master.close()
        except Exception:
            pass
