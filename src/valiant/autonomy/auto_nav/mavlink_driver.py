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
        nav = cfg.get("auto_nav", {})
        metric = cfg.get("metric_recon", {})
        self._base_approach_speed = nav.get("approach_speed", 0.3)
        self._slow_start_m = nav.get("approach_slow_start_m", 1.5)
        self._min_speed_factor = nav.get("approach_min_speed_factor", 0.25)
        self._fire_distance_m = metric.get("fire_distance_m", 0.8)

    def scaled_approach_speed(self, distance_m: float | None) -> float:
        """Reduce forward speed as the drone nears fire distance."""
        if distance_m is None:
            return self._base_approach_speed

        if distance_m >= self._slow_start_m:
            return self._base_approach_speed

        span = max(self._slow_start_m - self._fire_distance_m, 0.1)
        t = (distance_m - self._fire_distance_m) / span
        t = max(0.0, min(1.0, t))
        factor = self._min_speed_factor + (1.0 - self._min_speed_factor) * t
        return self._base_approach_speed * factor

    def move_toward_target(
        self,
        packet: MetricPacket,
        frame_w: int,
        frame_h: int,
        *,
        approach_speed: float | None = None,
        camera_down: bool = True,
    ) -> None:
        px, py = packet.target_px
        vel_right, vel_vertical = self.servo.compute_velocity(px, py, frame_w, frame_h)
        speed = approach_speed
        if speed is None:
            speed = self.scaled_approach_speed(packet.distance_m)
        if camera_down:
            self.servo.send_velocity_body(-vel_vertical, vel_right, speed)
        else:
            self.servo.send_velocity_body(speed, vel_right, vel_vertical)

    def hold_center(self, packet: MetricPacket, frame_w: int, frame_h: int, *, camera_down: bool = True) -> None:
        px, py = packet.target_px
        vel_right, vel_vertical = self.servo.compute_velocity(px, py, frame_w, frame_h)
        if camera_down:
            self.servo.send_velocity_body(-vel_vertical, vel_right, 0.0)
        else:
            self.servo.send_velocity_body(0.0, vel_right, vel_vertical)

    def stop(self) -> None:
        self.servo.stop()
