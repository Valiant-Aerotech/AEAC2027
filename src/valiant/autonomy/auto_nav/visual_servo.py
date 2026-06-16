"""PD visual servo controller for body-frame velocity commands."""

from __future__ import annotations

import math
import time

from pymavlink import mavutil


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
        self._use_local_ned = bool(sitl.get("velocity_local_ned", True))
        self._yaw_rad = 0.0
        self._last_err_x = 0.0
        self._last_err_y = 0.0
        self._last_time = time.time()
        self.last_vel_body = (0.0, 0.0, 0.0)

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
        vel_right = max(-self.max_vel, min(self.max_vel, vel_right))
        vel_vertical = max(-self.max_vel, min(self.max_vel, vel_vertical))
        return vel_right, vel_vertical

    def send_velocity_body(self, vel_x: float, vel_y: float, vel_z: float = 0.0) -> None:
        self.last_vel_body = (vel_x, vel_y, vel_z)
        type_mask = (
            mavutil.mavlink.POSITION_TARGET_TYPEMASK_X_IGNORE
            | mavutil.mavlink.POSITION_TARGET_TYPEMASK_Y_IGNORE
            | mavutil.mavlink.POSITION_TARGET_TYPEMASK_Z_IGNORE
            | mavutil.mavlink.POSITION_TARGET_TYPEMASK_AX_IGNORE
            | mavutil.mavlink.POSITION_TARGET_TYPEMASK_AY_IGNORE
            | mavutil.mavlink.POSITION_TARGET_TYPEMASK_AZ_IGNORE
            | mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_IGNORE
            | mavutil.mavlink.POSITION_TARGET_TYPEMASK_YAW_RATE_IGNORE
        )
        if self._use_local_ned:
            yaw = self._yaw_rad
            vn = math.cos(yaw) * vel_x - math.sin(yaw) * vel_y
            ve = math.sin(yaw) * vel_x + math.cos(yaw) * vel_y
            frame = mavutil.mavlink.MAV_FRAME_LOCAL_NED
            out_vx, out_vy, out_vz = vn, ve, vel_z
        else:
            frame = mavutil.mavlink.MAV_FRAME_BODY_NED
            out_vx, out_vy, out_vz = vel_x, vel_y, vel_z

        time_boot_ms = 0
        from valiant.common.mavlink_io import mavlink_io

        with mavlink_io(self.mav):
            self.mav.mav.set_position_target_local_ned_send(
                time_boot_ms,
                self.mav.target_system,
                self.mav.target_component,
                frame,
                type_mask,
                0,
                0,
                0,
                out_vx,
                out_vy,
                out_vz,
                0,
                0,
                0,
                0,
                0,
            )

    def stop(self) -> None:
        self.last_vel_body = (0.0, 0.0, 0.0)
        self.send_velocity_body(0.0, 0.0, 0.0)

    def resend_last_velocity(self) -> None:
        vx, vy, vz = self.last_vel_body
        if abs(vx) + abs(vy) + abs(vz) < 1e-6:
            return
        self.send_velocity_body(vx, vy, vz)
