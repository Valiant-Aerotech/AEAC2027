"""MAVLink helpers for SITL guided flight (velocity stream)."""

from __future__ import annotations

import threading
import time


class VelocityStream:
    """Resend last GUIDED target at fixed rate (ArduPilot needs ~10+ Hz)."""

    def __init__(self, servo, *, rate_hz: float = 20.0):
        self._servo = servo
        self._interval = 1.0 / rate_hz
        self._active = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._active = True
        self._thread = threading.Thread(target=self._loop, name="mavlink-vel-stream", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._active = False

    def _loop(self) -> None:
        while self._active:
            self._servo.resend_last_guided()
            time.sleep(self._interval)
