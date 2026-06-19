"""ArduCam ToF depth reader with graceful SDK fallback."""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

try:
    from ArducamDepthCamera import ArducamCamera, DepthData, FrameType

    HAVE_ARDUCAM = True
except ImportError:
    HAVE_ARDUCAM = False


class ArducamTofReader:
    """Wrap ArducamDepthCamera; depth frames as uint16 millimetres."""

    def __init__(self, *, amplitude_min: int = 30):
        self.amplitude_min = amplitude_min
        self._camera = None
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def start(self) -> bool:
        if not HAVE_ARDUCAM:
            print("[ToF] ArducamDepthCamera not installed - depth disabled")
            return False
        try:
            cam = ArducamCamera()
            if hasattr(cam, "open"):
                cam.open()
                cam.start(FrameType.DEPTH)
            else:
                cam.init()
                cam.start()
            self._camera = cam
            self._active = True
            print("[ToF] ArduCam ToF: active")
            return True
        except Exception as exc:
            print(f"[ToF] ArduCam start failed: {exc}")
            self._camera = None
            self._active = False
            return False

    def read_depth_mm(self) -> npt.NDArray[np.uint16] | None:
        if not self._active or self._camera is None:
            return None
        try:
            frame = self._camera.request_frame(2000)
            if frame is None:
                return None
            depth = self._frame_to_mm(frame)
            self._camera.release_frame(frame)
            return depth
        except Exception as exc:
            print(f"[ToF] frame read error: {exc}")
            return None

    def _frame_to_mm(self, frame) -> npt.NDArray[np.uint16]:
        if isinstance(frame, DepthData):
            depth_m = np.asarray(frame.depth_data, dtype=np.float32)
            amp = np.asarray(frame.amplitude_data, dtype=np.float32)
            mm = np.clip(depth_m * 1000.0, 0, 65535).astype(np.uint16)
            if amp.size == mm.size:
                mm[amp < self.amplitude_min] = 0
            return mm
        arr = np.asarray(frame, dtype=np.float32)
        return np.clip(arr * 1000.0, 0, 65535).astype(np.uint16)

    def median_depth_mm(self, depth_mm: npt.NDArray[np.uint16] | None) -> int | None:
        if depth_mm is None:
            return None
        valid = depth_mm[(depth_mm > 0) & (depth_mm < 60000)]
        if valid.size == 0:
            return None
        return int(np.median(valid))

    def stop(self) -> None:
        if self._camera is not None:
            try:
                self._camera.stop()
                if hasattr(self._camera, "close"):
                    self._camera.close()
            except Exception:
                pass
        self._camera = None
        self._active = False
