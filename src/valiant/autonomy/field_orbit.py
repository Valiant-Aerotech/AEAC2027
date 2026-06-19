"""Field orbit mission: GUIDED-triggered altitude hold, forward, circle, LOITER."""

from __future__ import annotations

import math
import time
from enum import Enum

from pymavlink import mavutil

from valiant.autonomy.gcs_hud import GcsHudReporter, format_orbit_status
from valiant.autonomy.guided_motion import GuidedMotionRunner
from valiant.autonomy.orbit_math import (
    circle_center,
    orbit_velocity_ned,
    update_lap_progress,
    velocity_toward_ned,
)
from valiant.autonomy.sitl_preflight import (
    _flight_mode_from_heartbeat,
    ensure_guided,
    wait_for_guided_trigger,
)
from valiant.autonomy.telemetry_bridge import TelemetryBridge
from valiant.common.mavlink import (
    connect,
    gcs_statustext_options_from_cfg,
    request_guided_telemetry_streams,
)
from valiant.common.mavlink_io import mavlink_io
from valiant.common.sitl_physics import wait_vehicle_pose


class OrbitPhase(str, Enum):
    STANDBY = "STANDBY"
    ALT_HOLD = "ALT_HOLD"
    FORWARD = "FORWARD"
    ORBIT = "ORBIT"
    RETURN_CENTER = "RETURN_CENTER"
    LOITER = "LOITER"
    DONE = "DONE"
    ABORT = "ABORT"


def _orbit_cfg(cfg: dict) -> dict:
    return cfg.get("field_orbit", {})


def _direction_clockwise(direction: str) -> bool:
    return direction.lower() in ("clockwise", "cw")


class FieldOrbitRunner:
    """Pilot-triggered GUIDED orbit: hold alt, forward, circle, return, LOITER."""

    def __init__(
        self,
        master: mavutil.mavfile,
        cfg: dict,
        *,
        hud: GcsHudReporter | None = None,
        telemetry: TelemetryBridge | None = None,
        sitl: bool = False,
        skip_standby: bool = False,
    ):
        self.master = master
        self.cfg = cfg
        self._ocfg = _orbit_cfg(cfg)
        self._hud = hud
        self._telemetry = telemetry
        self._sitl = sitl
        self._skip_standby = skip_standby
        self._phase = OrbitPhase.STANDBY
        self._laps = 0.0
        self._lap_target = float(self._ocfg.get("laps", 5))
        self._radius_err = 0.0
        self._start_time: float | None = None
        self._origin: tuple[float, float] | None = None
        self._center: tuple[float, float] | None = None
        self._clockwise = _direction_clockwise(str(self._ocfg.get("direction", "clockwise")))
        self._motion = GuidedMotionRunner(
            master,
            cfg,
            hud=hud,
            log_tag="Orbit",
            speed_m_s=float(self._ocfg.get("forward_speed_m_s", 0.45)),
            ensure_guided=lambda: ensure_guided(master, force=True),
        )

    @property
    def phase(self) -> OrbitPhase:
        return self._phase

    def _set_phase(self, phase: OrbitPhase, *, message: str | None = None) -> None:
        self._phase = phase
        if message:
            self._motion.say(message)
        elif phase != OrbitPhase.STANDBY:
            self._motion.say(format_orbit_status(phase.value, self._laps, self._lap_target))

    def _telemetry_send(self, pose) -> None:
        if self._telemetry is None:
            return
        alt_m = -pose.z if pose.ok else None
        self._telemetry.send(
            state=self._phase.value,
            sitl=self._sitl,
            vel_body=self._motion.servo.last_vel_body,
            extra={
                "phase": self._phase.value,
                "lap": round(self._laps, 2),
                "laps_target": self._lap_target,
                "radius_err_m": round(self._radius_err, 2),
                "alt_m": alt_m,
                "pos_x": pose.x if pose.ok else None,
                "pos_y": pose.y if pose.ok else None,
            },
        )

    def _in_guided(self) -> bool:
        with mavlink_io(self.master):
            hb = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=0.3)
        if hb is None or hb.get_srcSystem() != self.master.target_system:
            return self.master.flightmode == "GUIDED"
        return _flight_mode_from_heartbeat(self.master, hb) == "GUIDED"

    def _abort_if_left_guided(self) -> bool:
        if self._in_guided():
            return False
        self._motion.stop_stream()
        self._set_phase(OrbitPhase.ABORT, message="Aborted - left GUIDED")
        self._phase = OrbitPhase.STANDBY
        return True

    def _geofence_ok(self, x: float, y: float) -> bool:
        if not self.cfg.get("safety", {}).get("geofence_abort", True):
            return True
        if self._origin is None:
            return True
        limit = float(self._ocfg.get("geofence_radius_m", 12.0))
        ox, oy = self._origin
        return math.hypot(x - ox, y - oy) <= limit

    def _duration_ok(self) -> bool:
        max_s = float(self._ocfg.get("max_duration_s", 600))
        if max_s <= 0 or self._start_time is None:
            return True
        return (time.time() - self._start_time) <= max_s

    def _wait_trigger(self) -> tuple[float, float, float, float]:
        trigger_alt = float(self._ocfg.get("trigger_alt_m", 10.0))
        tol = float(self._ocfg.get("alt_tolerance_m", 0.35))
        require_gps = bool(self.cfg.get("flight", {}).get("require_gps", True))
        if self._skip_standby:
            pose = wait_vehicle_pose(
                self.master,
                need_position=True,
                need_attitude=True,
            )
            return pose.x, pose.y, pose.z, pose.yaw
        self._set_phase(OrbitPhase.STANDBY, message="Waiting for GUIDED at altitude")
        return wait_for_guided_trigger(
            self.master,
            min_alt_m=trigger_alt,
            alt_tolerance_m=tol,
            require_gps=require_gps,
            on_standby=lambda **kw: self._telemetry_send(kw.get("pose")),
        )

    def run(self) -> None:
        request_guided_telemetry_streams(self.master)
        x0, y0, z0, psi0 = self._wait_trigger()
        self._origin = (x0, y0)
        self._start_time = time.time()
        trigger_alt = float(self._ocfg.get("trigger_alt_m", 10.0))
        tol = float(self._ocfg.get("alt_tolerance_m", 0.35))
        forward_m = float(self._ocfg.get("forward_m", 2.0))
        radius_m = float(self._ocfg.get("radius_m", 5.0))
        orbit_speed = float(self._ocfg.get("orbit_speed_m_s", 0.40))
        radial_kp = float(self._ocfg.get("radial_kp", 0.25))
        center_tol = float(self._ocfg.get("center_tolerance_m", 0.5))

        pose = wait_vehicle_pose(self.master, need_position=True, need_attitude=True)
        self._motion.set_last_pose(pose)

        alt_agl = -z0
        if abs(alt_agl - trigger_alt) > tol:
            self._set_phase(OrbitPhase.ALT_HOLD, message=f"Climbing to {trigger_alt:.0f} m")
            self._motion.hold_altitude(
                trigger_alt,
                tolerance_m=tol,
                label=f"Climbing to {trigger_alt:.0f} m",
            )
        if self._abort_if_left_guided():
            return

        self._set_phase(OrbitPhase.FORWARD, message=f"Flying forward {forward_m:.0f} m")
        self._motion.drive_forward(forward_m, label=f"Flying forward {forward_m:.0f} m")
        if self._abort_if_left_guided():
            return

        pose = self._motion.pose(need_position=True, need_attitude=True)
        p1x, p1y = pose.x, pose.y
        cx, cy = circle_center(p1x, p1y, psi0, radius_m, clockwise=self._clockwise)
        self._center = (cx, cy)
        print(f"[Orbit] Center ({cx:.1f}, {cy:.1f}) R={radius_m:.1f} m")

        self._set_phase(OrbitPhase.ORBIT, message="Starting orbit")
        lap_progress = 0.0
        phi_prev: float | None = None
        last_lap_int = 0
        deadline = time.time() + max(
            120.0,
            self._lap_target * 2 * math.pi * radius_m / max(orbit_speed, 0.1) * 1.5,
        )
        self._motion.stop_stream()
        while time.time() < deadline:
            if self._abort_if_left_guided():
                return
            if not self._duration_ok():
                self._motion.say("Max duration - switching to loiter")
                break
            pose = self._motion.pose(pose, need_position=True)
            if not pose.ok:
                time.sleep(0.05)
                continue
            if not self._geofence_ok(pose.x, pose.y):
                self._motion.say("Geofence - switching to loiter")
                break
            vn, ve, err_r = orbit_velocity_ned(
                pose.x,
                pose.y,
                cx,
                cy,
                radius_m,
                orbit_speed,
                radial_kp,
                clockwise=self._clockwise,
            )
            self._radius_err = err_r
            vz = self._motion.altitude_vz(trigger_alt)
            self._motion.servo.send_velocity_ned(vn, ve, vz)
            self._motion.start_stream()
            lap_progress, self._laps, phi_prev = update_lap_progress(
                pose.x,
                pose.y,
                cx,
                cy,
                phi_prev,
                lap_progress,
                clockwise=self._clockwise,
            )
            lap_int = int(self._laps)
            if lap_int > last_lap_int:
                last_lap_int = lap_int
                self._motion.say(
                    format_orbit_status("ORBIT", self._laps, self._lap_target),
                    force=True,
                )
            self._telemetry_send(pose)
            if self._laps >= self._lap_target:
                break
            time.sleep(0.05)
        self._motion.stop_stream()

        if self._abort_if_left_guided():
            return

        self._set_phase(OrbitPhase.RETURN_CENTER, message="Returning to center")
        return_speed = float(self._ocfg.get("return_speed_m_s", orbit_speed))
        deadline = time.time() + 120.0
        self._motion.stop_stream()
        while time.time() < deadline:
            if self._abort_if_left_guided():
                return
            pose = self._motion.pose(pose, need_position=True)
            if not pose.ok:
                time.sleep(0.05)
                continue
            dist = math.hypot(pose.x - cx, pose.y - cy)
            if dist < center_tol:
                break
            vn, ve = velocity_toward_ned(pose.x, pose.y, cx, cy, return_speed)
            vz = self._motion.altitude_vz(trigger_alt)
            self._motion.servo.send_velocity_ned(vn, ve, vz)
            self._motion.start_stream()
            self._telemetry_send(pose)
            time.sleep(0.05)
        self._motion.stop_stream()

        self._set_phase(OrbitPhase.LOITER)
        try:
            self._motion.set_loiter()
        except RuntimeError:
            self._motion.say("LOITER unavailable - stopping commands")
        self._phase = OrbitPhase.DONE
        self._motion.say("Orbit complete - manual control")
        self._telemetry_send(pose)
        time.sleep(2.0)


def run_field_orbit(
    *,
    connection: str,
    cfg: dict,
    sitl: bool = False,
    skip_preflight: bool = False,
    skip_standby: bool = False,
    takeoff_alt_m: float | None = None,
    gcs_ip: str | None = None,
) -> None:
    """Connect and run the field orbit sequence."""
    from valiant.autonomy.sitl_preflight import arm_guided_takeoff

    baud = int(cfg.get("mavlink", {}).get("baud", 57600))
    master = connect(connection, baud)
    gcs_cfg = cfg.get("gcs_monitor", {})
    hud = GcsHudReporter(
        master,
        interval_s=float(gcs_cfg.get("statustext_interval_s", 2.0)),
        options=gcs_statustext_options_from_cfg(cfg, sitl=sitl),
    )
    telemetry: TelemetryBridge | None = None
    ip = gcs_ip or gcs_cfg.get("ip")
    if ip:
        telemetry = TelemetryBridge(ip, port=int(gcs_cfg.get("port", 14560)))
    try:
        if sitl and not skip_preflight:
            alt = takeoff_alt_m
            if alt is None:
                alt = float(cfg.get("sitl", {}).get("takeoff_alt_m", 5.0))
            arm_guided_takeoff(
                master,
                takeoff_alt_m=alt,
                timeout_s=float(cfg.get("sitl", {}).get("preflight_timeout_s", 75.0)),
                ekf_wait_s=float(cfg.get("sitl", {}).get("ekf_wait_s", 45.0)),
            )
            skip_standby = True
        request_guided_telemetry_streams(master)
        runner = FieldOrbitRunner(
            master,
            cfg,
            hud=hud,
            telemetry=telemetry,
            sitl=sitl,
            skip_standby=skip_standby or (sitl and skip_preflight),
        )
        runner.run()
    finally:
        hud.close()
        if telemetry is not None:
            telemetry.close()
        try:
            master.close()
        except Exception:
            pass
