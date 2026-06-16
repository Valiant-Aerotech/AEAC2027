"""One-axis pitch gimbal using MAV_CMD_DO_SET_SERVO."""

from __future__ import annotations

import time

from pymavlink import mavutil


class GimbalController:
    """Map vertical pixel error to gimbal pitch PWM."""

    def __init__(self, master: mavutil.mavfile | None, cfg: dict):
        gimbal = cfg.get("gimbal", {})
        self.enabled = bool(gimbal.get("enabled", False))
        self.master = master
        self.channel = int(gimbal.get("channel", 9))
        self.pwm_min = int(gimbal.get("pwm_min", 1000))
        self.pwm_max = int(gimbal.get("pwm_max", 2000))
        self.pwm_neutral = int(gimbal.get("pwm_neutral", 1500))
        self.kp = float(gimbal.get("kp", 0.8))
        self.deadband_px = int(gimbal.get("deadband_px", 40))
        self.min_interval_s = float(gimbal.get("min_interval_s", 0.1))
        self._current_pwm = self.pwm_neutral
        self._last_send = 0.0

        if self.enabled:
            print(
                f"[Gimbal] Pitch axis on SERVO{self.channel} "
                f"PWM {self.pwm_min}-{self.pwm_max} neutral={self.pwm_neutral}"
            )

    @property
    def active(self) -> bool:
        return self.enabled and self.master is not None

    def reset(self) -> None:
        self._current_pwm = self.pwm_neutral
        if self.active:
            self._send_pwm(self.pwm_neutral, force=True)

    @property
    def current_pwm(self) -> int:
        return self._current_pwm

    def center_pitch(self, cy: int, frame_h: int, *, send: bool = True) -> int:
        """Adjust gimbal PWM from vertical pixel error. Returns commanded PWM."""
        if not self.enabled:
            return self.pwm_neutral

        err_y = cy - frame_h // 2
        if abs(err_y) < self.deadband_px:
            pwm = self._current_pwm
        else:
            pwm = int(self._current_pwm - self.kp * err_y)
            pwm = max(self.pwm_min, min(self.pwm_max, pwm))

        self._current_pwm = pwm
        if send and self.active:
            self._send_pwm(pwm)
        return pwm

    def _send_pwm(self, pwm: int, *, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_send < self.min_interval_s:
            return
        self._last_send = now
        self.master.mav.command_long_send(
            self.master.target_system,
            self.master.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0,
            self.channel,
            float(pwm),
            0,
            0,
            0,
            0,
            0,
        )

    def cleanup(self) -> None:
        if self.active:
            self._send_pwm(self.pwm_neutral, force=True)
