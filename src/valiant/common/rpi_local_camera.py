"""Picamera2 RGB capture with optional ArduCam ToF on Raspberry Pi."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

try:
    from picamera2 import Picamera2

    HAVE_PICAMERA2 = True
except ImportError:
    HAVE_PICAMERA2 = False

from valiant.common.sensors.arducam_tof import ArducamTofReader


class RpiLocalCamera:
    """Onboard camera facade: RGB frame + optional depth mm array."""

    def __init__(
        self,
        *,
        width: int = 640,
        height: int = 480,
        tof_enabled: bool = True,
        tof_amplitude_min: int = 30,
    ):
        self.width = width
        self.height = height
        self._picam = None
        self._tof = ArducamTofReader(amplitude_min=tof_amplitude_min) if tof_enabled else None
        self._last_depth_mm: npt.NDArray[np.uint16] | None = None
        self._started = False

    @classmethod
    def from_config(cls, cfg: dict) -> RpiLocalCamera:
        cam = cfg.get("camera", {})
        rpi = cam.get("rpi", {})
        tof = rpi.get("tof", {})
        return cls(
            width=int(rpi.get("width", 640)),
            height=int(rpi.get("height", 480)),
            tof_enabled=bool(tof.get("enabled", True)),
            tof_amplitude_min=int(tof.get("amplitude_min", 30)),
        )

    def start(self) -> None:
        if not HAVE_PICAMERA2:
            raise RuntimeError(
                "picamera2 not available. On Pi: sudo apt install python3-picamera2"
            )
        self._picam = Picamera2()
        config = self._picam.create_still_configuration(
            main={"size": (self.width, self.height), "format": "RGB888"}
        )
        self._picam.configure(config)
        self._picam.start()
        if self._tof is not None:
            self._tof.start()
        self._started = True
        print(f"[Camera] RPi local RGB {self.width}x{self.height}")

    def get_frame(self) -> np.ndarray | None:
        if not self._started or self._picam is None:
            return None
        frame = self._picam.capture_array()
        if self._tof is not None and self._tof.active:
            self._last_depth_mm = self._tof.read_depth_mm()
        return frame

    @property
    def depth_mm(self) -> npt.NDArray[np.uint16] | None:
        return self._last_depth_mm

    @property
    def depth_ok(self) -> bool:
        return self._tof is not None and self._tof.active

    def cleanup(self) -> None:
        if self._tof is not None:
            self._tof.stop()
        if self._picam is not None:
            try:
                self._picam.stop()
            except Exception:
                pass
        self._picam = None
        self._started = False
