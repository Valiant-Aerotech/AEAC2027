"""VL53L1X / MAVLink rangefinder reader."""

from __future__ import annotations

import time
from threading import Event, Lock, Thread
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymavlink import mavutil


class RangefinderReader:
    """Background MAVLink reader for DISTANCE_SENSOR / RANGEFINDER messages."""

    def __init__(self, master: mavutil.mavfile, cfg: dict):
        self.master = master
        self.cfg = cfg
        self._distance_m: float | None = None
        self._timestamp: float = 0.0
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._stale_after_s = cfg.get("metric_recon", {}).get("rangefinder_stale_s", 1.0)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._loop, name="RangefinderReader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def read_distance_m(self) -> float | None:
        with self._lock:
            if self._distance_m is None:
                return None
            if time.time() - self._timestamp > self._stale_after_s:
                return None
            return self._distance_m

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                msg = self.master.recv_match(
                    type=["DISTANCE_SENSOR", "RANGEFINDER"],
                    blocking=True,
                    timeout=0.5,
                )
            except Exception:
                continue
            if msg is None:
                continue
            self._handle_message(msg)

    def _handle_message(self, msg) -> None:
        msg_type = msg.get_type()
        distance_m: float | None = None

        if msg_type == "DISTANCE_SENSOR":
            # current_distance is centimetres in MAVLink spec
            distance_m = float(msg.current_distance) / 100.0
            if distance_m <= 0 or distance_m > 200.0:
                return
        elif msg_type == "RANGEFINDER":
            distance_m = float(msg.distance)
            if distance_m <= 0:
                return

        with self._lock:
            self._distance_m = distance_m
            self._timestamp = time.time()
