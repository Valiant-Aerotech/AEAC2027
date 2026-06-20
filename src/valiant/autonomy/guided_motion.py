"""Shared GUIDED motion: forward legs, yaw hold, altitude hold, LOITER handoff."""

from __future__ import annotations

import math
import time
from typing import Callable

from pymavlink import mavutil

from valiant.autonomy.auto_nav.mavlink_stream import VelocityStream
from valiant.autonomy.auto_nav.visual_servo import VisualServo
from valiant.autonomy.gcs_hud import GcsHudReporter
from valiant.autonomy.orbit_math import velocity_toward_ned, wrap_pi
from valiant.autonomy.pilot_override import OverrideKind, PilotOverrideMonitor
from valiant.common.mavlink import send_companion_heartbeat
from valiant.common.sitl_physics import drain_vehicle_pose, refresh_vehicle_pose, wait_vehicle_pose


class GuidedMotionRunner:
    """Pose polling, velocity streaming, and scripted GUIDED segments."""

    def __init__(
        self,
        master: mavutil.mavfile,
        cfg: dict,
        *,
        hud: GcsHudReporter | None = None,
        log_tag: str = "Motion",
        speed_m_s: float = 0.45,
        yaw_rate_rad_s: float = 0.35,
        ensure_guided: Callable[[], None] | None = None,
    ):
        self.master = master
        self.cfg = cfg
        self._hud = hud
        self._log_tag = log_tag
        self._speed = max(0.1, speed_m_s)
        self._yaw_rate = max(0.1, yaw_rate_rad_s)
        self._servo = VisualServo(master, cfg)
        self._stream = VelocityStream(self._servo, rate_hz=20.0)
        self._last_hb = 0.0
        self._last_pose = None
        self._z_hold: float | None = None
        self._ensure_guided = ensure_guided or (lambda: None)
        self._pilot_monitor: PilotOverrideMonitor | None = None

    def set_pilot_monitor(self, monitor: PilotOverrideMonitor | None) -> None:
        self._pilot_monitor = monitor

    def check_pilot_override(self) -> OverrideKind:
        """Poll pilot override; stop velocity stream if active."""
        if self._pilot_monitor is None:
            return OverrideKind.NONE
        kind = self._pilot_monitor.poll()
        if kind != OverrideKind.NONE:
            self.stop_stream()
        return kind

    @property
    def servo(self) -> VisualServo:
        return self._servo

    @property
    def last_pose(self):
        return self._last_pose

    def set_last_pose(self, pose) -> None:
        self._last_pose = pose

    def set_z_hold(self, z_ned: float | None) -> None:
        """Hold this LOCAL NED z during orbit (None = use target altitude)."""
        self._z_hold = z_ned

    @staticmethod
    def altitude_label(current_alt_m: float, target_alt_m: float, *, tolerance_m: float = 0.35) -> str:
        if current_alt_m > target_alt_m + tolerance_m:
            return f"Descending to {target_alt_m:.0f} m"
        if current_alt_m < target_alt_m - tolerance_m:
            return f"Climbing to {target_alt_m:.0f} m"
        return f"Holding {target_alt_m:.0f} m"

    def say(self, message: str, *, force: bool = True) -> None:
        print(f"[{self._log_tag}] {message}")
        if self._hud is not None:
            self._hud.send(message, force=force)

    def heartbeat(self) -> None:
        now = time.time()
        if now - self._last_hb > 1.0:
            send_companion_heartbeat(self.master)
            self._last_hb = now

    def pose(
        self,
        previous=None,
        *,
        need_position: bool = False,
        need_attitude: bool = False,
        fresh: bool = False,
    ):
        self.heartbeat()
        if fresh or (not need_position and not need_attitude):
            pose = refresh_vehicle_pose(self.master, previous or self._last_pose)
        elif need_position or need_attitude:
            pose = wait_vehicle_pose(
                self.master,
                timeout_s=15.0,
                need_position=need_position,
                need_attitude=need_attitude,
                previous=previous or self._last_pose,
            )
        else:
            pose = drain_vehicle_pose(self.master, previous or self._last_pose)
        self._last_pose = pose
        if pose.ok:
            self._servo.set_yaw_rad(pose.yaw)
        return pose

    def refresh_pose(self, previous=None):
        """Drain inbox for latest LOCAL NED (20 Hz control loops)."""
        return self.pose(previous, fresh=True)

    def stop_stream(self) -> None:
        self._stream.stop()
        self._servo.clear_stream_target()

    def start_stream(self) -> None:
        self._stream.start()

    def ensure_guided_mode(self) -> None:
        self._ensure_guided()

    def drive_to_ned_point(
        self,
        target_x: float,
        target_y: float,
        *,
        label: str,
        speed: float | None = None,
        arrival_m: float | None = None,
        timeout_s: float | None = None,
        anchor_xy: tuple[float, float] | None = None,
    ) -> tuple[float, float]:
        """Drive toward a LOCAL NED waypoint; return (x, y) at end."""
        orbit_cfg = self.cfg.get("field_orbit", {})
        spd = max(0.1, speed if speed is not None else self._speed)
        arrive = float(
            arrival_m if arrival_m is not None else orbit_cfg.get("forward_arrival_m", 0.25)
        )
        self.say(label)
        self.ensure_guided_mode()
        self.stop_stream()
        if self._last_pose is None or not self._last_pose.ok:
            self._last_pose = wait_vehicle_pose(
                self.master,
                need_position=True,
                need_attitude=True,
            )
        pose = self._last_pose
        start_x, start_y = pose.x, pose.y
        if anchor_xy is None:
            anchor_xy = (start_x, start_y)
        ax, ay = anchor_xy
        dist_plan = math.hypot(target_x - start_x, target_y - start_y)
        if timeout_s is not None:
            max_s = timeout_s
        elif orbit_cfg.get("forward_timeout_s") is not None:
            max_s = float(orbit_cfg["forward_timeout_s"])
        else:
            max_s = dist_plan / spd * 1.5 + 3.0
        deadline = time.time() + max_s
        last_log = 0.0
        log_interval_s = 2.0
        while time.time() < deadline:
            if self.check_pilot_override() != OverrideKind.NONE:
                return pose.x, pose.y
            self.stop_stream()
            pose = self.refresh_pose(pose)
            if not pose.ok:
                time.sleep(0.05)
                continue
            remaining = math.hypot(target_x - pose.x, target_y - pose.y)
            traveled = math.hypot(pose.x - ax, pose.y - ay)
            now = time.time()
            if now - last_log >= log_interval_s:
                print(
                    f"[{self._log_tag}] forward remaining={remaining:.2f}m "
                    f"traveled={traveled:.2f}m from anchor"
                )
                last_log = now
            if remaining <= arrive:
                print(
                    f"[{self._log_tag}] forward arrival at "
                    f"({pose.x:.2f},{pose.y:.2f}) err={remaining:.2f}m"
                )
                break
            vn, ve = velocity_toward_ned(pose.x, pose.y, target_x, target_y, spd)
            self._servo.send_velocity_ned(vn, ve, 0.0)
            self.start_stream()
            time.sleep(0.05)
        else:
            remaining = math.hypot(target_x - pose.x, target_y - pose.y)
            print(
                f"[{self._log_tag}] forward timed out at ({pose.x:.2f},{pose.y:.2f}) "
                f"remaining={remaining:.2f}m"
            )
        self.stop_stream()
        time.sleep(0.3)
        return pose.x, pose.y

    def drive_forward_anchored(
        self,
        anchor_x: float,
        anchor_y: float,
        yaw_rad: float,
        distance_m: float,
        *,
        label: str,
        arrival_m: float | None = None,
        timeout_s: float | None = None,
    ) -> tuple[float, float]:
        """Drive forward_m along anchor heading (body frame), measuring from anchor."""
        orbit_cfg = self.cfg.get("field_orbit", {})
        arrive = float(
            arrival_m if arrival_m is not None else orbit_cfg.get("forward_arrival_m", 0.25)
        )
        self.say(label)
        self.ensure_guided_mode()
        self.stop_stream()
        if self._last_pose is None or not self._last_pose.ok:
            self._last_pose = wait_vehicle_pose(
                self.master,
                need_position=True,
                need_attitude=True,
            )
        pose = self._last_pose
        self._servo.set_yaw_rad(yaw_rad)
        self._servo.send_guided_yaw(yaw_rad)
        if timeout_s is not None:
            max_s = timeout_s
        elif orbit_cfg.get("forward_timeout_s") is not None:
            max_s = float(orbit_cfg["forward_timeout_s"])
        else:
            max_s = distance_m / self._speed * 1.5 + 3.0
        deadline = time.time() + max_s
        last_log = 0.0
        log_interval_s = 2.0
        self._servo.send_velocity_body(self._speed, 0.0, 0.0)
        self.start_stream()
        while time.time() < deadline:
            if self.check_pilot_override() != OverrideKind.NONE:
                return pose.x, pose.y
            self.stop_stream()
            pose = self.refresh_pose(pose)
            along = math.cos(yaw_rad) * (pose.x - anchor_x) + math.sin(yaw_rad) * (
                pose.y - anchor_y
            )
            remaining = max(0.0, distance_m - along)
            now = time.time()
            if now - last_log >= log_interval_s:
                print(
                    f"[{self._log_tag}] forward along={along:.2f}m "
                    f"remaining={remaining:.2f}m from anchor"
                )
                last_log = now
            if along >= distance_m - arrive:
                print(
                    f"[{self._log_tag}] forward arrival along={along:.2f}m "
                    f"pos=({pose.x:.2f},{pose.y:.2f})"
                )
                break
            self._servo.send_velocity_body(self._speed, 0.0, 0.0)
            self.start_stream()
            time.sleep(0.05)
        else:
            along = math.cos(yaw_rad) * (pose.x - anchor_x) + math.sin(yaw_rad) * (
                pose.y - anchor_y
            )
            print(
                f"[{self._log_tag}] forward timed out along={along:.2f}m "
                f"target={distance_m:.2f}m"
            )
        self.stop_stream()
        time.sleep(0.3)
        return pose.x, pose.y

    def drive_forward(self, distance_m: float, *, label: str) -> tuple[float, float]:
        """Return (x, y) at end of leg along current heading."""
        if self._last_pose is None or not self._last_pose.ok:
            self._last_pose = wait_vehicle_pose(
                self.master,
                need_position=True,
                need_attitude=True,
            )
        pose = self._last_pose
        target_x = pose.x + distance_m * math.cos(pose.yaw)
        target_y = pose.y + distance_m * math.sin(pose.yaw)
        return self.drive_to_ned_point(
            target_x,
            target_y,
            label=label,
            anchor_xy=(pose.x, pose.y),
        )

    def turn_degrees(self, degrees: float, *, label: str) -> None:
        self.say(label)
        self.ensure_guided_mode()
        self.stop_stream()
        pose = self.pose(need_attitude=True)
        target_yaw = wrap_pi(pose.yaw + math.radians(degrees))
        print(
            f"[{self._log_tag}] Yaw hold -> {math.degrees(target_yaw):.0f} deg "
            f"({abs(degrees):.0f} deg {'CW' if degrees >= 0 else 'CCW'})"
        )
        self._servo.send_guided_yaw(target_yaw)
        self.start_stream()
        deadline = time.time() + max(
            45.0,
            abs(degrees) / max(math.degrees(self._yaw_rate), 10.0) * 4.0,
        )
        while time.time() < deadline:
            if self.check_pilot_override() != OverrideKind.NONE:
                break
            pose = self.pose(pose)
            err = abs(wrap_pi(pose.yaw - target_yaw))
            if err < math.radians(4.0):
                print(f"[{self._log_tag}] Turn complete (err {math.degrees(err):.1f} deg)")
                break
            time.sleep(0.05)
        else:
            err = abs(wrap_pi(pose.yaw - target_yaw))
            print(f"[{self._log_tag}] Warning: turn timed out (err {math.degrees(err):.1f} deg)")
        self.stop_stream()
        time.sleep(0.3)

    def hold_altitude(
        self,
        target_alt_m: float,
        *,
        tolerance_m: float = 0.35,
        stable_s: float = 1.0,
        label: str = "Holding altitude",
        max_duration_s: float = 60.0,
        log_interval_s: float = 2.0,
    ) -> bool:
        """Hold target AGL until within tolerance for stable_s. Returns success."""
        self.say(label)
        self.ensure_guided_mode()
        orbit_cfg = self.cfg.get("field_orbit", {})
        kp_z = float(orbit_cfg.get("altitude_kp", self.cfg.get("sitl", {}).get("altitude_kp", 0.22)))
        max_vz = float(orbit_cfg.get("max_vz", self.cfg.get("sitl", {}).get("max_vz", 0.15)))
        z_target = -target_alt_m
        stable_since: float | None = None
        deadline = time.time() + max_duration_s
        last_log = 0.0
        self.stop_stream()
        while time.time() < deadline:
            if self.check_pilot_override() != OverrideKind.NONE:
                break
            self.stop_stream()
            pose = self.refresh_pose(self._last_pose)
            if not pose.ok:
                time.sleep(0.05)
                continue
            alt_m = -pose.z
            err_z = z_target - pose.z
            now = time.time()
            if now - last_log >= log_interval_s:
                print(
                    f"[{self._log_tag}] alt={alt_m:.1f}m target={target_alt_m:.1f}m "
                    f"err={abs(alt_m - target_alt_m):.2f}m"
                )
                last_log = now
            if abs(err_z) < tolerance_m:
                if stable_since is None:
                    stable_since = now
                elif now - stable_since >= stable_s:
                    print(f"[{self._log_tag}] Altitude hold OK at {alt_m:.1f}m")
                    self.stop_stream()
                    return True
            else:
                stable_since = None
            vz = max(-max_vz, min(max_vz, kp_z * err_z))
            self._servo.send_velocity_body(0.0, 0.0, vz)
            self.start_stream()
            time.sleep(0.05)
        alt_m = -self._last_pose.z if self._last_pose and self._last_pose.ok else 0.0
        print(f"[{self._log_tag}] Altitude hold timed out at {alt_m:.1f}m")
        self.stop_stream()
        return False

    def altitude_vz(
        self,
        target_alt_m: float,
        *,
        tolerance_m: float = 0.35,
    ) -> float:
        """Vertical velocity command for ongoing altitude hold."""
        orbit_cfg = self.cfg.get("field_orbit", {})
        kp_z = float(orbit_cfg.get("altitude_kp", self.cfg.get("sitl", {}).get("altitude_kp", 0.22)))
        max_vz = float(orbit_cfg.get("max_vz", self.cfg.get("sitl", {}).get("max_vz", 0.15)))
        if self._last_pose is None or not self._last_pose.ok:
            return 0.0
        z_target = self._z_hold if self._z_hold is not None else -target_alt_m
        err_z = z_target - self._last_pose.z
        if abs(err_z) < tolerance_m:
            return 0.0
        return max(-max_vz, min(max_vz, kp_z * err_z))

    def set_loiter(self, *, message: str = "Loiter - manual control") -> None:
        self.stop_stream()
        mapping = self.master.mode_mapping()
        if "LOITER" not in mapping:
            raise RuntimeError(f"LOITER not available: {mapping}")
        self.say(message)
        self.master.set_mode(mapping["LOITER"])
        deadline = time.time() + 8.0
        want = mapping["LOITER"]
        while time.time() < deadline:
            self.heartbeat()
            hb = self.master.recv_match(type="HEARTBEAT", blocking=True, timeout=1.0)
            if hb is not None and hb.get_srcSystem() == self.master.target_system:
                if hb.custom_mode == want:
                    return
        print(f"[{self._log_tag}] Warning: LOITER not confirmed")

    def hold_hover_at_altitude(
        self,
        target_alt_m: float,
        *,
        duration_s: float = 2.0,
        tolerance_m: float = 0.35,
    ) -> bool:
        """Zero horizontal velocity with altitude hold before mode handoff."""
        deadline = time.time() + duration_s
        self.stop_stream()
        while time.time() < deadline:
            if self.check_pilot_override() != OverrideKind.NONE:
                return False
            self.stop_stream()
            pose = self.refresh_pose(self._last_pose)
            if not pose.ok:
                time.sleep(0.05)
                continue
            vz = self.altitude_vz(target_alt_m, tolerance_m=tolerance_m)
            self._servo.send_velocity_ned(0.0, 0.0, vz)
            self.start_stream()
            time.sleep(0.05)
        self.stop_stream()
        return True
