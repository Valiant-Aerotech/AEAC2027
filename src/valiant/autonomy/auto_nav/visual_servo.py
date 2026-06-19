"""PD visual servo controller for body-frame velocity commands."""

from __future__ import annotations

import math
import time

from pymavlink import mavutil

# ArduPilot GUIDED SET_POSITION_TARGET_LOCAL_NED masks (see copter-commands-in-guided-mode)
GUIDED_MASK_VELOCITY = 3527  # 0x0DC7
GUIDED_MASK_YAW = 2503  # yaw target + zero velocity
GUIDED_MASK_YAW_RATE = 1479  # yaw rate + zero velocity


class VisualServo:
    """Proportional-derivative visual servoing controller."""

    def __init__(self, mav_connection: mavutil.mavfile, cfg: dict):
        self.mav = mav_connection
        nav = cfg.get("auto_nav", {})
        sitl = cfg.get("sitl", {})
        self.kp_x = nav.get("kp_x", 0.002)
        self.kp_y = nav.get("kp_y", 0.002)
        self.kd_x = nav.get("kd_x", 0.0)
        self.kd_y = nav.get("kd_y", 0.0)
        self.max_vel = nav.get("max_vel", 0.5)
        self.deadband_px = nav.get("deadband_px", 40)
        self._vel_smooth = float(nav.get("vel_smooth", 0.0))
        self._use_local_ned = bool(sitl.get("velocity_local_ned", True))
        self._yaw_rad = 0.0
        self._last_err_x = 0.0
        self._last_err_y = 0.0
        self._last_time = time.time()
        self._smooth_right = 0.0
        self._smooth_vertical = 0.0
        self.last_vel_body = (0.0, 0.0, 0.0)
        self._stream_mode: str | None = None
        self._last_yaw_target: float | None = None
        self._last_yaw_rate = 0.0
        self.last_vel_ned = (0.0, 0.0, 0.0)

    def set_yaw_rad(self, yaw_rad: float) -> None:
        self._yaw_rad = yaw_rad

    def compute_velocity(self, cx: int, cy: int, frame_w: int, frame_h: int):
        now = time.time()
        dt = max(now - self._last_time, 1e-6)
        self._last_time = now

        err_x = cx - frame_w // 2
        err_y = cy - frame_h // 2
        derr_x = (err_x - self._last_err_x) / dt
        derr_y = (err_y - self._last_err_y) / dt
        self._last_err_x = err_x
        self._last_err_y = err_y

        vel_right = self.kp_x * err_x + self.kd_x * derr_x
        vel_vertical = self.kp_y * err_y + self.kd_y * derr_y

        if abs(err_x) < self.deadband_px:
            vel_right *= abs(err_x) / max(self.deadband_px, 1)
        if abs(err_y) < self.deadband_px:
            vel_vertical *= abs(err_y) / max(self.deadband_px, 1)

        if self._vel_smooth > 0.0:
            a = min(max(self._vel_smooth, 0.0), 1.0)
            vel_right = a * vel_right + (1.0 - a) * self._smooth_right
            vel_vertical = a * vel_vertical + (1.0 - a) * self._smooth_vertical
            self._smooth_right = vel_right
            self._smooth_vertical = vel_vertical

        vel_right = max(-self.max_vel, min(self.max_vel, vel_right))
        vel_vertical = max(-self.max_vel, min(self.max_vel, vel_vertical))
        return vel_right, vel_vertical

    def _send_position_target(
        self,
        *,
        frame: int,
        type_mask: int,
        vx: float,
        vy: float,
        vz: float,
        yaw: float,
        yaw_rate: float,
    ) -> None:
        from valiant.common.mavlink_io import mavlink_io

        with mavlink_io(self.mav):
            self.mav.mav.set_position_target_local_ned_send(
                0,
                self.mav.target_system,
                self.mav.target_component,
                frame,
                type_mask,
                0,
                0,
                0,
                vx,
                vy,
                vz,
                0,
                0,
                0,
                yaw,
                yaw_rate,
            )

    def send_velocity_ned(self, vn: float, ve: float, vz: float = 0.0) -> None:
        """Horizontal/vertical velocity in LOCAL NED (for orbit tangential commands)."""
        self.last_vel_ned = (vn, ve, vz)
        self.last_vel_body = (0.0, 0.0, 0.0)
        self._stream_mode = "velocity_ned"
        self._last_yaw_target = None
        self._last_yaw_rate = 0.0
        self._send_position_target(
            frame=mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            type_mask=GUIDED_MASK_VELOCITY,
            vx=vn,
            vy=ve,
            vz=vz,
            yaw=0.0,
            yaw_rate=0.0,
        )

    def send_velocity_body(self, vel_x: float, vel_y: float, vel_z: float = 0.0) -> None:
        self.last_vel_body = (vel_x, vel_y, vel_z)
        self.last_vel_ned = (0.0, 0.0, 0.0)
        self._stream_mode = "velocity"
        self._last_yaw_target = None
        self._last_yaw_rate = 0.0
        type_mask = GUIDED_MASK_VELOCITY
        if self._use_local_ned:
            yaw = self._yaw_rad
            vn = math.cos(yaw) * vel_x - math.sin(yaw) * vel_y
            ve = math.sin(yaw) * vel_x + math.cos(yaw) * vel_y
            frame = mavutil.mavlink.MAV_FRAME_LOCAL_NED
            out_vx, out_vy, out_vz = vn, ve, vel_z
        else:
            frame = mavutil.mavlink.MAV_FRAME_BODY_NED
            out_vx, out_vy, out_vz = vel_x, vel_y, vel_z

        self._send_position_target(
            frame=frame,
            type_mask=type_mask,
            vx=out_vx,
            vy=out_vy,
            vz=out_vz,
            yaw=0.0,
            yaw_rate=0.0,
        )

    def send_guided_yaw(self, yaw_rad: float) -> None:
        """Hold absolute heading in GUIDED (LOCAL_NED + zero velocity + yaw)."""
        self._stream_mode = "yaw"
        self._last_yaw_target = yaw_rad
        self.last_vel_body = (0.0, 0.0, 0.0)
        self._send_position_target(
            frame=mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            type_mask=GUIDED_MASK_YAW,
            vx=0.0,
            vy=0.0,
            vz=0.0,
            yaw=yaw_rad,
            yaw_rate=0.0,
        )

    def send_yaw_rate(self, yaw_rate: float) -> None:
        """Rotate in place in GUIDED (zero velocity + yaw rate)."""
        self._stream_mode = "yaw_rate"
        self._last_yaw_rate = yaw_rate
        self._last_yaw_target = None
        self.last_vel_body = (0.0, 0.0, 0.0)
        self._send_position_target(
            frame=mavutil.mavlink.MAV_FRAME_LOCAL_NED,
            type_mask=GUIDED_MASK_YAW_RATE,
            vx=0.0,
            vy=0.0,
            vz=0.0,
            yaw=0.0,
            yaw_rate=yaw_rate,
        )

    def clear_stream_target(self) -> None:
        """Stop streaming without sending a conflicting GUIDED target."""
        self._stream_mode = None
        self._last_yaw_target = None
        self._last_yaw_rate = 0.0

    def stop(self) -> None:
        self.last_vel_body = (0.0, 0.0, 0.0)
        self._smooth_right = 0.0
        self._smooth_vertical = 0.0
        self._stream_mode = "velocity"
        self._last_yaw_target = None
        self.send_velocity_body(0.0, 0.0, 0.0)

    def resend_last_guided(self) -> None:
        """Resend active velocity, yaw-hold, or yaw-rate command (for 20 Hz stream)."""
        if self._stream_mode == "yaw" and self._last_yaw_target is not None:
            self.send_guided_yaw(self._last_yaw_target)
            return
        if self._stream_mode == "yaw_rate" and abs(self._last_yaw_rate) > 1e-6:
            self.send_yaw_rate(self._last_yaw_rate)
            return
        if self._stream_mode == "velocity_ned":
            vn, ve, vz = self.last_vel_ned
            if abs(vn) + abs(ve) + abs(vz) < 1e-6:
                return
            self.send_velocity_ned(vn, ve, vz)
            return
        vx, vy, vz = self.last_vel_body
        if abs(vx) + abs(vy) + abs(vz) < 1e-6:
            return
        self.send_velocity_body(vx, vy, vz)

    def resend_last_velocity(self) -> None:
        self.resend_last_guided()
