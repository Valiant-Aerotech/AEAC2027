"""Field orbit mission: GUIDED-triggered altitude hold, forward, circle, LOITER."""

from __future__ import annotations

import math
import time
from enum import Enum

from pymavlink import mavutil

from valiant.autonomy.gcs_hud import GcsHudReporter, format_orbit_status
from valiant.autonomy.guided_motion import GuidedMotionRunner
from valiant.autonomy.orbit_math import (
    advance_arc_progress_m,
    circle_center,
    combined_laps,
    course_yaw_from_velocity,
    forward_entry_ned,
    limit_yaw_step,
    orbit_velocity_ned,
    update_lap_progress,
    velocity_toward_ned,
)
from valiant.autonomy.pilot_override import OverrideKind, PilotOverrideMonitor, override_message
from valiant.autonomy.sitl_preflight import (
    ensure_guided,
    wait_for_guided_trigger,
)
from valiant.autonomy.telemetry_bridge import TelemetryBridge
from valiant.common.mavlink import (
    connect,
    gcs_statustext_options_from_cfg,
    request_guided_telemetry_streams,
    send_land,
)
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
        self._anchor: tuple[float, float, float] | None = None
        self._center: tuple[float, float] | None = None
        self._clockwise = _direction_clockwise(str(self._ocfg.get("direction", "clockwise")))
        self._yaw_follow_velocity = bool(self._ocfg.get("yaw_follow_velocity", True))
        self._yaw_rate_max_deg_s = float(self._ocfg.get("yaw_rate_max_deg_s", 25.0))
        self._orbit_yaw_cmd: float | None = None
        self._orbit_aborted = False
        self._last_status_log = 0.0
        self._pilot_monitor = PilotOverrideMonitor(master, cfg)
        self._motion = GuidedMotionRunner(
            master,
            cfg,
            hud=hud,
            log_tag="Orbit",
            speed_m_s=float(self._ocfg.get("forward_speed_m_s", 0.45)),
            ensure_guided=lambda: ensure_guided(master, force=True),
        )
        self._motion.set_pilot_monitor(self._pilot_monitor)

    @property
    def phase(self) -> OrbitPhase:
        return self._phase

    def _set_phase(
        self,
        phase: OrbitPhase,
        *,
        message: str | None = None,
        silent: bool = False,
    ) -> None:
        self._phase = phase
        if silent:
            return
        if message:
            self._motion.say(message)
        elif phase != OrbitPhase.STANDBY:
            self._motion.say(format_orbit_status(phase.value, self._laps, self._lap_target))

    def _telemetry_send(self, pose, *, vn: float | None = None, ve: float | None = None) -> None:
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
                "vn": vn,
                "ve": ve,
            },
        )

    def _handle_pilot_override(self) -> str | None:
        """Stop companion commands on pilot override. Returns 'standby' if takeover."""
        kind = self._motion.check_pilot_override()
        if kind == OverrideKind.NONE:
            return None
        msg = override_message(kind)
        if msg:
            self._motion.say(msg)
        if kind in (OverrideKind.KILL_SWITCH, OverrideKind.EMERGENCY):
            pilot_cfg = self._ocfg.get("pilot", {})
            if pilot_cfg.get("companion_land_on_kill", False):
                try:
                    send_land(self.master)
                except Exception as exc:
                    print(f"[Orbit] Warning: companion LAND failed: {exc}")
        self._phase = OrbitPhase.STANDBY
        return "standby"

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

    def _abort_to_loiter(self, message: str) -> None:
        """Stop GUIDED velocity and hand off to LOITER (geofence / timeout)."""
        self._orbit_aborted = True
        self._motion.stop_stream()
        self._motion.say(message)
        kind = self._pilot_monitor.poll()
        if kind != OverrideKind.NONE:
            self._phase = OrbitPhase.STANDBY
            return
        try:
            self._motion.set_loiter()
        except RuntimeError:
            self._motion.say("LOITER unavailable - stopping commands")
        self._phase = OrbitPhase.DONE
        self._motion.say("Orbit complete - manual control")

    def _altitude_m(self, pose) -> float:
        return -pose.z if pose.ok else 0.0

    def _log_status(
        self,
        pose,
        phase: str,
        target_alt: float,
        *,
        vn: float | None = None,
        ve: float | None = None,
        orbit_elapsed_s: float | None = None,
        force: bool = False,
    ) -> None:
        now = time.time()
        if not force and now - self._last_status_log < 2.0:
            return
        self._last_status_log = now
        alt = self._altitude_m(pose)
        pos = f"pos=({pose.x:.2f},{pose.y:.2f})" if pose.ok else "pos=?"
        vel = ""
        if vn is not None and ve is not None:
            vel = f" vn={vn:.2f} ve={ve:.2f}"
        elapsed = ""
        if orbit_elapsed_s is not None:
            elapsed = f" t={orbit_elapsed_s:.0f}s"
        msg = (
            f"alt={alt:.1f}m target={target_alt:.1f}m phase={phase} "
            f"{pos}{vel}{elapsed} lap={self._laps:.1f}/{self._lap_target:.0f} "
            f"r_err={self._radius_err:.2f}m"
        )
        print(f"[Orbit] {msg}")

    def _send_orbit_velocity(
        self,
        vn: float,
        ve: float,
        vz: float,
        *,
        dt_s: float = 0.05,
    ) -> float | None:
        """Send NED velocity; optionally align yaw with course."""
        if not self._yaw_follow_velocity:
            self._orbit_yaw_cmd = None
            self._motion.servo.send_velocity_ned(vn, ve, vz)
            return None
        yaw_target = course_yaw_from_velocity(vn, ve)
        if self._orbit_yaw_cmd is None:
            self._orbit_yaw_cmd = yaw_target
        else:
            max_rate = math.radians(self._yaw_rate_max_deg_s)
            self._orbit_yaw_cmd = limit_yaw_step(
                yaw_target,
                self._orbit_yaw_cmd,
                max_rate_rad_s=max_rate,
                dt_s=dt_s,
            )
        self._motion.servo.send_velocity_ned_with_yaw(vn, ve, vz, self._orbit_yaw_cmd)
        return self._orbit_yaw_cmd

    def _ensure_at_altitude(self, target_alt: float, tol: float) -> bool:
        """Block until altitude is within tolerance; return False on timeout."""
        pose = self._motion.pose(need_position=True)
        alt = self._altitude_m(pose)
        if abs(alt - target_alt) <= tol:
            print(f"[Orbit] Already at {alt:.1f}m (target {target_alt:.1f}m)")
            self._motion.set_z_hold(-target_alt)
            return True
        alt_label = GuidedMotionRunner.altitude_label(alt, target_alt, tolerance_m=tol)
        self._set_phase(OrbitPhase.ALT_HOLD, message=alt_label)
        ok = self._motion.hold_altitude(
            target_alt,
            tolerance_m=tol,
            label=alt_label,
            max_duration_s=90.0,
        )
        if ok:
            self._motion.set_z_hold(-target_alt)
            return True
        pose = self._motion.pose(need_position=True)
        self._log_status(pose, "ALT_HOLD_FAIL", target_alt, force=True)
        self._motion.say(f"Alt hold failed at {self._altitude_m(pose):.1f}m")
        return False

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
        retrigger = bool(self._ocfg.get("standby_retrigger", True)) and not self._skip_standby
        while True:
            outcome = self._execute_mission()
            if outcome == "complete" or not retrigger:
                break
            if outcome == "standby":
                self._laps = 0.0
                self._radius_err = 0.0
                self._orbit_aborted = False
                print("[Orbit] Standby - waiting for next GUIDED trigger")
                continue
            break

    def _execute_mission(self) -> str:
        """Run one orbit cycle from GUIDED trigger through LOITER handoff."""
        x0, y0, z0, psi0 = self._wait_trigger()
        self._pilot_monitor.sync_from_vehicle()
        self._anchor = (x0, y0, psi0)
        self._origin = (x0, y0)
        self._start_time = time.time()
        trigger_alt = float(self._ocfg.get("trigger_alt_m", 10.0))
        tol = float(self._ocfg.get("alt_tolerance_m", 0.35))
        forward_m = float(self._ocfg.get("forward_m", 2.0))
        forward_arrival_m = float(self._ocfg.get("forward_arrival_m", 0.25))
        radius_m = float(self._ocfg.get("radius_m", 5.0))
        orbit_speed = float(self._ocfg.get("orbit_speed_m_s", 0.40))
        radial_kp = float(self._ocfg.get("radial_kp", 0.25))
        center_tol = float(self._ocfg.get("center_tolerance_m", 0.5))
        loiter_settle_s = float(self._ocfg.get("loiter_settle_s", 2.0))

        pose = wait_vehicle_pose(self.master, need_position=True, need_attitude=True)
        self._motion.set_last_pose(pose)
        self._log_status(pose, "START", trigger_alt, force=True)

        if not self._ensure_at_altitude(trigger_alt, tol):
            self._abort_to_loiter("Altitude not reached - loiter")
            return "complete"
        override = self._handle_pilot_override()
        if override:
            return override

        intent_x, intent_y = forward_entry_ned(x0, y0, psi0, forward_m)

        self._set_phase(OrbitPhase.FORWARD, silent=True)
        pose = self._motion.refresh_pose(self._motion.last_pose)
        along_forward = math.cos(psi0) * (pose.x - x0) + math.sin(psi0) * (pose.y - y0)
        if along_forward >= forward_m - forward_arrival_m:
            print(
                f"[Orbit] Already at forward entry "
                f"(along={along_forward:.2f}m target={forward_m:.2f}m)"
            )
        else:
            self._motion.drive_forward_anchored(
                x0,
                y0,
                psi0,
                forward_m,
                label=f"Flying forward {forward_m:.0f} m",
                arrival_m=forward_arrival_m,
            )
        override = self._handle_pilot_override()
        if override:
            return override

        pose = self._motion.pose(need_position=True, need_attitude=True)
        p1x, p1y = pose.x, pose.y
        entry_yaw = pose.yaw
        cx, cy = circle_center(p1x, p1y, entry_yaw, radius_m, clockwise=self._clockwise)
        self._center = (cx, cy)
        dist_entry = math.hypot(p1x - cx, p1y - cy)
        vn0, ve0, err_r0 = orbit_velocity_ned(
            p1x,
            p1y,
            cx,
            cy,
            radius_m,
            orbit_speed,
            radial_kp,
            clockwise=self._clockwise,
        )
        entry_radial_kp = float(self._ocfg.get("orbit_entry_radial_kp", radial_kp * 2.5))
        entry_blend_s = float(self._ocfg.get("orbit_entry_blend_s", 4.0))
        orbit_start = time.time()
        radius_latch_tol = float(self._ocfg.get("radius_latch_tol_m", 1.0))
        orbit_latched = False
        print(
            f"[Orbit] intent_entry=({intent_x:.1f},{intent_y:.1f}) "
            f"actual=({p1x:.1f},{p1y:.1f}) center=({cx:.1f},{cy:.1f}) "
            f"R={radius_m:.1f} m entry_dist={dist_entry:.2f}m err_r={err_r0:.2f} "
            f"vn={vn0:.2f} ve={ve0:.2f} yaw={math.degrees(entry_yaw):.0f}deg "
            f"alt={self._altitude_m(pose):.1f}m"
        )

        self._set_phase(OrbitPhase.ORBIT, message="Starting orbit")
        request_guided_telemetry_streams(self.master)
        self._orbit_yaw_cmd = entry_yaw
        lap_progress = 0.0
        arc_progress_m = 0.0
        phi_prev: float | None = None
        last_lap_int = 0
        orbit_tick_dt = 0.05
        last_px, last_py = pose.x, pose.y
        stale_pose_ticks = 0
        return_on_timeout = bool(self._ocfg.get("return_on_timeout", False))
        deadline = time.time() + max(
            120.0,
            self._lap_target * 2 * math.pi * radius_m / max(orbit_speed, 0.1) * 1.5,
        )
        self._motion.stop_stream()
        orbit_exit = "timeout"
        while time.time() < deadline:
            override = self._handle_pilot_override()
            if override:
                return override
            if not self._duration_ok():
                self._abort_to_loiter("Max duration - switching to loiter")
                return "complete"
            self._motion.stop_stream()
            pose = self._motion.refresh_pose(pose)
            if not pose.ok:
                time.sleep(orbit_tick_dt)
                continue
            moved = math.hypot(pose.x - last_px, pose.y - last_py)
            if moved < 0.02:
                stale_pose_ticks += 1
                if stale_pose_ticks >= 40:
                    print("[Orbit] WARN: pose stale >2s - re-requesting telemetry")
                    request_guided_telemetry_streams(self.master)
                    stale_pose_ticks = 0
            else:
                stale_pose_ticks = 0
                last_px, last_py = pose.x, pose.y
            if not self._geofence_ok(pose.x, pose.y):
                orbit_exit = "geofence"
                self._abort_to_loiter("Geofence - switching to loiter")
                return "complete"
            blend = max(0.0, 1.0 - (time.time() - orbit_start) / max(entry_blend_s, 0.1))
            effective_radial = radial_kp + (entry_radial_kp - radial_kp) * blend
            vn, ve, err_r = orbit_velocity_ned(
                pose.x,
                pose.y,
                cx,
                cy,
                radius_m,
                orbit_speed,
                effective_radial,
                clockwise=self._clockwise,
            )
            self._radius_err = err_r
            vz = self._motion.altitude_vz(trigger_alt, tolerance_m=tol)
            yaw_cmd = self._send_orbit_velocity(vn, ve, vz, dt_s=orbit_tick_dt)
            self._motion.start_stream()
            orbit_elapsed = time.time() - orbit_start
            self._log_status(
                pose,
                "ORBIT",
                trigger_alt,
                vn=vn,
                ve=ve,
                orbit_elapsed_s=orbit_elapsed,
            )
            if abs(err_r) <= radius_latch_tol:
                if not orbit_latched:
                    orbit_latched = True
                    phi_prev = None
                    lap_progress = 0.0
                    arc_progress_m = 0.0
                    print(f"[Orbit] On radius (err_r={err_r:.2f}m) - lap counting active")
                lap_progress, _, phi_prev = update_lap_progress(
                    pose.x,
                    pose.y,
                    cx,
                    cy,
                    phi_prev,
                    lap_progress,
                    clockwise=self._clockwise,
                )
                if moved >= 0.02:
                    arc_progress_m = advance_arc_progress_m(
                        arc_progress_m, vn, ve, orbit_tick_dt
                    )
                self._laps = combined_laps(lap_progress, arc_progress_m, radius_m)
            else:
                self._laps = 0.0
            lap_int = int(self._laps)
            if lap_int > last_lap_int:
                last_lap_int = lap_int
                self._motion.say(
                    format_orbit_status("ORBIT", self._laps, self._lap_target),
                    force=True,
                )
            self._telemetry_send(pose, vn=vn, ve=ve)
            if self._laps >= self._lap_target:
                orbit_exit = "lap complete"
                break
            time.sleep(orbit_tick_dt)
        self._motion.stop_stream()
        print(
            f"[Orbit] Orbit exit: {orbit_exit} lap={self._laps:.1f}/{self._lap_target:.0f} "
            f"pos=({pose.x:.2f},{pose.y:.2f})"
        )

        override = self._handle_pilot_override()
        if override:
            return override

        if self._laps < self._lap_target and not return_on_timeout:
            self._abort_to_loiter(
                f"Orbit incomplete (lap={self._laps:.1f}/{self._lap_target:.0f}) - loiter"
            )
            return "complete"

        self._set_phase(OrbitPhase.RETURN_CENTER, message="Returning to center")
        return_speed = float(self._ocfg.get("return_speed_m_s", orbit_speed))
        deadline = time.time() + 120.0
        self._motion.stop_stream()
        while time.time() < deadline:
            override = self._handle_pilot_override()
            if override:
                return override
            pose = self._motion.refresh_pose(pose)
            if not pose.ok:
                time.sleep(0.05)
                continue
            dist = math.hypot(pose.x - cx, pose.y - cy)
            if dist < center_tol:
                break
            vn, ve = velocity_toward_ned(pose.x, pose.y, cx, cy, return_speed)
            vz = self._motion.altitude_vz(trigger_alt, tolerance_m=tol)
            self._send_orbit_velocity(vn, ve, vz, dt_s=0.05)
            self._motion.start_stream()
            self._log_status(pose, "RETURN", trigger_alt, vn=vn, ve=ve)
            self._telemetry_send(pose, vn=vn, ve=ve)
            time.sleep(0.05)
        self._motion.stop_stream()

        override = self._handle_pilot_override()
        if override:
            return override

        self._motion.hold_hover_at_altitude(
            trigger_alt,
            duration_s=loiter_settle_s,
            tolerance_m=tol,
        )
        override = self._handle_pilot_override()
        if override:
            return override

        self._set_phase(OrbitPhase.LOITER, silent=True)
        try:
            self._motion.set_loiter()
        except RuntimeError:
            self._motion.say("LOITER unavailable - stopping commands")
        self._phase = OrbitPhase.DONE
        self._motion.say("Orbit complete - manual control")
        self._telemetry_send(pose)
        time.sleep(2.0)
        return "complete"


def run_field_orbit(
    *,
    connection: str,
    cfg: dict,
    sitl: bool = False,
    skip_preflight: bool = False,
    skip_standby: bool = False,
    takeoff_alt_m: float | None = None,
    gcs_ip: str | None = None,
    skip_safety_check: bool = False,
) -> None:
    """Connect and run the field orbit sequence."""
    from valiant.autonomy.flight.fc_safety import SafetyPreflightError, assert_safety_lua
    from valiant.autonomy.sitl_preflight import arm_guided_takeoff
    from valiant.common.mavlink import MavlinkConnectError, connect, print_mavlink_connect_error

    baud = int(cfg.get("mavlink", {}).get("baud", 57600))
    try:
        master = connect(connection, baud)
    except MavlinkConnectError as exc:
        print_mavlink_connect_error(exc, prefix="[Orbit]")
        raise SystemExit(1) from None
    if not sitl and not skip_safety_check:
        try:
            assert_safety_lua(master, cfg, sitl=False)
        except SafetyPreflightError:
            try:
                master.close()
            except Exception:
                pass
            raise SystemExit(1) from None
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
            trigger = float(cfg.get("field_orbit", {}).get("trigger_alt_m", alt))
            if abs(trigger - alt) > 0.01:
                print(f"[Orbit] SITL takeoff at {alt:.0f}m; orbit target alt {trigger:.0f}m")
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
