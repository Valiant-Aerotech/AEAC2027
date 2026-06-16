"""MAVLink motion command driver for Auto-Nav."""

from __future__ import annotations

from pymavlink import mavutil

from valiant.autonomy.auto_nav.mavlink_stream import VelocityStream
from valiant.autonomy.auto_nav.visual_servo import VisualServo
from valiant.autonomy.packets import MetricPacket


class MavlinkDriver:
    """Translate MetricPacket into MAVLink velocity commands."""

    def __init__(self, master: mavutil.mavfile, cfg: dict):
        self.master = master
        self.servo = VisualServo(master, cfg)
        self.cfg = cfg
        self._gimbal_pitch = bool(cfg.get("gimbal", {}).get("enabled", False))
        self._vel_stream = VelocityStream(self.servo)

    def start_velocity_stream(self) -> None:
        self._vel_stream.start()

    def stop_velocity_stream(self) -> None:
        self._vel_stream.stop()

    def move_toward_target(
        self,
        packet: MetricPacket,
        frame_w: int,
        frame_h: int,
        *,
        approach_speed: float = 0.3,
        camera_down: bool = True,
        vz_ned: float = 0.0,
    ) -> None:
        self._vel_stream.start()
        px, py = packet.target_px
        vel_right, vel_vertical = self.servo.compute_velocity(px, py, frame_w, frame_h)
        if self._gimbal_pitch:
            self.servo.send_velocity_body(approach_speed, vel_right, vz_ned)
            return
        if camera_down:
            self.servo.send_velocity_body(-vel_vertical, vel_right, approach_speed + vz_ned)
        else:
            self.servo.send_velocity_body(approach_speed, vel_right, vel_vertical + vz_ned)

    def hold_center(
        self,
        packet: MetricPacket,
        frame_w: int,
        frame_h: int,
        *,
        camera_down: bool = True,
        vz_ned: float = 0.0,
    ) -> None:
        px, py = packet.target_px
        vel_right, vel_vertical = self.servo.compute_velocity(px, py, frame_w, frame_h)
        if self._gimbal_pitch:
            self.servo.send_velocity_body(0.0, vel_right, vz_ned)
            return
        if camera_down:
            self.servo.send_velocity_body(-vel_vertical, vel_right, vz_ned)
        else:
            self.servo.send_velocity_body(0.0, vel_right, vel_vertical + vz_ned)

    def stop(self) -> None:
        self._vel_stream.stop()
        self.servo.stop()

    def search_velocity(self, vx: float, vy: float, vz: float = 0.0) -> None:
        self._vel_stream.start()
        self.servo.send_velocity_body(vx, vy, vz)

    def search_motion(
        self,
        vx: float,
        vy: float,
        vz: float = 0.0,
        *,
        yaw_rate: float | None = None,
    ) -> None:
        self._vel_stream.start()
        if yaw_rate is not None and abs(yaw_rate) > 1e-4:
            if abs(vx) + abs(vy) + abs(vz) > 1e-4:
                self.servo.send_velocity_body(vx, vy, vz)
            else:
                self.servo.send_yaw_rate(yaw_rate)
        else:
            self.servo.send_velocity_body(vx, vy, vz)
