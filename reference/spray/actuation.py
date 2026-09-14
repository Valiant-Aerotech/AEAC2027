"""Water trigger actuation - MAVLink servo or GPIO."""

from __future__ import annotations

import time

from pymavlink import mavutil


class WaterTrigger:
    """Fire water using MAVLink servo or GPIO relay."""

    def __init__(self, mav_connection: mavutil.mavfile | None, cfg: dict):
        self.mav = mav_connection
        self.cfg = cfg.get("spray", {})
        self.method = self.cfg.get("method", "MAVLINK_SERVO")
        self._gpio = None
        self._gpio_setup()

    def _gpio_setup(self) -> None:
        if self.method != "GPIO":
            return
        try:
            import RPi.GPIO as GPIO  # type: ignore

            pin = self.cfg.get("gpio_pin", 18)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(pin, GPIO.OUT)
            GPIO.output(pin, GPIO.LOW)
            self._gpio = GPIO
            self._gpio_pin = pin
            print(f"[WATER] GPIO mode - pin {pin} ready")
        except (ImportError, RuntimeError) as exc:
            print(f"[WATER] WARNING: RPi.GPIO unavailable ({exc})")

    def fire(self, duration: float | None = None) -> None:
        if self.method in (None, "none", "NONE", ""):
            print("[WATER] Spray disabled (method none)")
            return
        duration = duration if duration is not None else self.cfg.get("duration_s", 2.0)
        print(f"[WATER] Firing for {duration:.1f}s via {self.method}")
        if self.method == "GPIO":
            self._fire_gpio(duration)
        elif self.method == "MAVLINK_SERVO":
            self._fire_mavlink(duration)
        else:
            print(f"[WATER] Unknown method '{self.method}'")

    def _fire_gpio(self, duration: float) -> None:
        if self._gpio is None:
            print("[WATER] SIMULATED GPIO fire")
            time.sleep(duration)
            return
        self._gpio.output(self._gpio_pin, self._gpio.HIGH)
        time.sleep(duration)
        self._gpio.output(self._gpio_pin, self._gpio.LOW)

    def _fire_mavlink(self, duration: float) -> None:
        if self.mav is None:
            print("[WATER] SIMULATED MAVLink fire")
            time.sleep(duration)
            return
        channel = self.cfg.get("channel", 15)
        pwm_open = self.cfg.get("pwm_open", 1900)
        pwm_close = self.cfg.get("pwm_close", 1100)
        self.mav.mav.command_long_send(
            self.mav.target_system, self.mav.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0, channel, pwm_open, 0, 0, 0, 0, 0,
        )
        time.sleep(duration)
        self.mav.mav.command_long_send(
            self.mav.target_system, self.mav.target_component,
            mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
            0, channel, pwm_close, 0, 0, 0, 0, 0,
        )

    def cleanup(self) -> None:
        if self.method == "GPIO" and self._gpio is not None:
            try:
                self._gpio.cleanup()
            except Exception:
                pass
