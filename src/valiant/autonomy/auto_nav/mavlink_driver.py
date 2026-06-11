"""MAVLink motion command driver for Auto-Nav."""

from __future__ import annotations

from pymavlink import mavutil

from valiant.autonomy.auto_nav.visual_servo import VisualServo
from valiant.autonomy.packets import MetricPacket


class MavlinkDriver:
    """Translate MetricPacket into MAVLink velocity commands."""

    def __init__(self, master: mavutil.mavfile, cfg: dict):
        self.master = master
        self.servo = VisualServo(master, cfg)
        self.cfg = cfg

    def move_toward_target(
        self,
        packet: MetricPacket,
        frame_w: int,
        frame_h: int,
        *,
        approach_speed: float = 0.3,
        camera_down: bool = True,
    ) -> None:
        px, py = packet.target_px
        vel_right, vel_vertical = self.servo.compute_velocity(px, py, frame_w, frame_h)
        if camera_down:
            self.servo.send_velocity_body(-vel_vertical, vel_right, approach_speed)
        else:
            self.servo.send_velocity_body(approach_speed, vel_right, vel_vertical)

    def hold_center(self, packet: MetricPacket, frame_w: int, frame_h: int, *, camera_down: bool = True) -> None:
        px, py = packet.target_px
        vel_right, vel_vertical = self.servo.compute_velocity(px, py, frame_w, frame_h)
        if camera_down:
            self.servo.send_velocity_body(-vel_vertical, vel_right, 0.0)
        else:
            self.servo.send_velocity_body(0.0, vel_right, vel_vertical)

    def stop(self) -> None:
        self.servo.stop()
