"""ArduCam ToF depth reader for Raspberry Pi (optional SDK)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class ArducamTofConfig:
    enabled: bool = True
    connect: str = "CSI"  # CSI | USB
    camera_index: int = 0
    request_timeout_ms: int = 200
    min_amplitude: int = 30
    max_depth_m: float = 6.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArducamTofConfig:
        return cls(
            enabled=data.get("enabled", True),
            connect=str(data.get("connect", "CSI")).upper(),
            camera_index=int(data.get("camera_index", 0)),
            request_timeout_ms=int(data.get("request_timeout_ms", 200)),
            min_amplitude=int(data.get("min_amplitude", 30)),
            max_depth_m=float(data.get("max_depth_m", 6.0)),
        )


class ArducamTofReader:
    """Capture uint16 depth frames (millimeters) from Arducam ToF SDK."""

    def __init__(self, cfg: ArducamTofConfig):
        self.cfg = cfg
        self._cam = None
        self._ac = None
        self._opened = False

    @property
    def is_available(self) -> bool:
        return self._opened

    def start(self) -> bool:
        if not self.cfg.enabled:
            return False
        try:
            import ArducamDepthCamera as ac  # type: ignore[import-untyped]
        except ImportError:
            print(
                "[ArducamTof] ArducamDepthCamera not installed. "
                "Run hardware/vion/rpi/install_arducam_tof.sh on the Pi."
            )
            return False

        self._ac = ac
        cam = ac.ArducamCamera()
        connect = ac.TOFConnect.CSI if self.cfg.connect == "CSI" else ac.TOFConnect.USB

        # SDK versions differ: init() vs open()+start()
        if hasattr(cam, "init"):
            rc = cam.init(connect, ac.TOFOutput.DEPTH, self.cfg.camera_index)
            if rc != 0:
                print(f"[ArducamTof] init failed (rc={rc})")
                return False
            if cam.start() != 0:
                print("[ArducamTof] start failed")
                return False
        else:
            if cam.open(connect, self.cfg.camera_index) != 0:
                print("[ArducamTof] open failed")
                return False
            if cam.start(ac.TOFOutput.DEPTH) != 0:
                print("[ArducamTof] start(DEPTH) failed")
                return False

        self._cam = cam
        self._opened = True
        print("[ArducamTof] depth camera started")
        return True

    def capture_depth_mm(self) -> np.ndarray | None:
        if not self._opened or self._cam is None or self._ac is None:
            return None

        ac = self._ac
        frame = self._cam.requestFrame(self.cfg.request_timeout_ms)
        if frame is None:
            return None

        try:
            depth_buf = frame.getDepthData()
            depth_mm = self._depth_to_mm(depth_buf)

            if hasattr(frame, "getAmplitudeData"):
                amp = frame.getAmplitudeData()
                if amp is not None:
                    mask = amp < self.cfg.min_amplitude
                    depth_mm[mask] = 0
        finally:
            self._cam.releaseFrame(frame)

        return depth_mm

    def _depth_to_mm(self, depth_buf: np.ndarray) -> np.ndarray:
        depth_m = np.nan_to_num(depth_buf.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
        valid = depth_m[depth_m > 0]
        if valid.size and float(np.median(valid)) > 20:
            depth_mm = depth_m.astype(np.uint16)
        else:
            depth_mm = (depth_m * 1000.0).astype(np.uint16)

        max_mm = int(self.cfg.max_depth_m * 1000)
        depth_mm[depth_mm > max_mm] = 0
        return depth_mm

    def stop(self) -> None:
        if self._cam is None:
            return
        try:
            self._cam.stop()
        except Exception:
            pass
        try:
            self._cam.close()
        except Exception:
            pass
        self._cam = None
        self._opened = False
