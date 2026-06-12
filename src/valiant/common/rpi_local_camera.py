"""Onboard Raspberry Pi camera: RGB + ArduCam ToF depth."""

from __future__ import annotations

import platform
import time
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt


class RpiLocalCamera:
    """Capture RGB frames and optional depth from Pi sensors.

    On a non-Pi dev machine, falls back to USB webcam for RGB only (depth None).
    Full depth capture requires Pi hardware and ArduCam SDK (see hardware/vion/rpi/).
    """

    def __init__(
        self,
        cfg: dict,
        *,
        webcam_fallback_index: int = 0,
        recording_dir: str | None = None,
    ):
        self.cfg = cfg
        cam_cfg = cfg.get("camera", {})
        rpi_cfg = cam_cfg.get("rpi", {})
        self.rgb_width = rpi_cfg.get("rgb_width", 640)
        self.rgb_height = rpi_cfg.get("rgb_height", 480)
        self._recording_dir = recording_dir
        self._depth_mm: npt.NDArray[np.uint16] | None = None
        self._picam = None
        self._webcam = None
        self._recording_depth = None

        if self._is_raspberry_pi():
            self._init_pi_camera(rpi_cfg)
        else:
            self._init_webcam_fallback(webcam_fallback_index)

        if recording_dir:
            from valiant.autonomy.metric_recon.depth_source import RecordingDepthSource

            self._recording_depth = RecordingDepthSource(recording_dir)

    @staticmethod
    def _is_raspberry_pi() -> bool:
        return platform.system() == "Linux" and "arm" in platform.machine().lower()

    def _init_pi_camera(self, rpi_cfg: dict) -> None:
        try:
            from picamera2 import Picamera2  # type: ignore[import-untyped]

            self._picam = Picamera2()
            config = self._picam.create_preview_configuration(
                main={"size": (self.rgb_width, self.rgb_height), "format": "RGB888"}
            )
            self._picam.configure(config)
            self._picam.start()
            time.sleep(0.5)
            print("[RpiLocalCamera] Picamera2 started")
        except ImportError:
            print("[RpiLocalCamera] picamera2 not installed; using webcam fallback")
            self._init_webcam_fallback(0)
        except Exception as exc:
            print(f"[RpiLocalCamera] Picamera2 failed ({exc}); using webcam fallback")
            self._init_webcam_fallback(0)

        # ArduCam ToF depth is loaded per-frame when SDK is wired on Pi.
        # Until hardware bring-up, depth stays None and metric recon uses FOV fallback.

    def _init_webcam_fallback(self, camera_index: int) -> None:
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        self._webcam = cv2.VideoCapture(camera_index, backend)
        if not self._webcam.isOpened():
            raise RuntimeError(
                f"Could not open camera index {camera_index} for rpi_local dev fallback"
            )
        print(f"[RpiLocalCamera] Dev fallback webcam index {camera_index}")

    @classmethod
    def from_config(
        cls,
        cfg: dict,
        *,
        webcam_fallback_index: int = 0,
        recording_dir: str | None = None,
    ) -> RpiLocalCamera:
        cam_cfg = cfg.get("camera", {})
        rpi_cfg = cam_cfg.get("rpi", {})
        rec = recording_dir or rpi_cfg.get("recording_dir")
        return cls(
            cfg,
            webcam_fallback_index=webcam_fallback_index,
            recording_dir=rec,
        )

    def get_frame(self) -> npt.NDArray[np.uint8] | None:
        if self._picam is not None:
            try:
                rgb = self._picam.capture_array()
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            except Exception:
                return None

        if self._webcam is not None:
            ret, frame = self._webcam.read()
            return frame if ret else None

        return None

    def get_depth_mm(self) -> npt.NDArray[np.uint16] | None:
        if self._depth_mm is not None:
            return self._depth_mm
        if self._recording_depth is not None:
            return self._recording_depth.get_depth_mm()
        return None

    def set_depth_mm(self, depth_mm: npt.NDArray[np.uint16] | None) -> None:
        """Inject depth from ArduCam driver (called by Pi sensor loop)."""
        self._depth_mm = depth_mm

    def cleanup(self) -> None:
        if self._picam is not None:
            try:
                self._picam.stop()
            except Exception:
                pass
            self._picam = None
        if self._webcam is not None:
            self._webcam.release()
            self._webcam = None
        if self._recording_depth is not None:
            self._recording_depth.stop()
            self._recording_depth = None
