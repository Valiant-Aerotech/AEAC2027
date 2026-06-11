"""scrcpy window capture for GCS-offload camera feed."""

from __future__ import annotations

import os
import subprocess
import time
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    import numpy.typing as npt

try:
    import mss
    import pygetwindow as gw

    HAVE_SCREEN_CAPTURE = True
except ImportError:
    HAVE_SCREEN_CAPTURE = False


class ScrcpyCamera:
    """Capture frames from a scrcpy mirror window."""

    def __init__(
        self,
        window_title: str = "ExtinguisherCam",
        phone_ip: str | None = None,
        *,
        max_fps: int | None = 30,
        max_size: int | None = 1280,
        video_bit_rate_mbps: int | None = 8,
        no_audio: bool = True,
        min_grab_interval_s: float = 0.0,
    ):
        if not HAVE_SCREEN_CAPTURE:
            raise RuntimeError(
                "mss and pygetwindow required. Run: pip install mss pygetwindow"
            )
        self.window_title = window_title
        self.min_grab_interval_s = min_grab_interval_s
        self._last_grab_time = 0.0
        self.sct = mss.mss()
        self.window = None
        self.scrcpy_proc: subprocess.Popen | None = None

        if os.name == "nt":
            subprocess.run(["taskkill", "/IM", "scrcpy.exe", "/F"], capture_output=True)

        c_flags = 0x08000000 if os.name == "nt" else 0

        if phone_ip:
            subprocess.run(
                ["adb", "connect", phone_ip],
                capture_output=True,
                creationflags=c_flags,
            )

        scrcpy_args = ["scrcpy", "--stay-awake", f"--window-title={window_title}"]
        if no_audio:
            scrcpy_args.append("--no-audio")
        if max_fps:
            scrcpy_args.append(f"--max-fps={max_fps}")
        if max_size:
            scrcpy_args.append(f"--max-size={max_size}")
        if video_bit_rate_mbps:
            scrcpy_args.append(f"--video-bit-rate={video_bit_rate_mbps}M")

        try:
            self.scrcpy_proc = subprocess.Popen(
                scrcpy_args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=c_flags,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "scrcpy not found on PATH. Install scrcpy before running Task 2."
            ) from exc

    @classmethod
    def from_config(cls, cfg: dict, *, phone_ip: str | None = None) -> ScrcpyCamera:
        """Build a camera from merged drone config."""
        cam_cfg = cfg.get("camera", {})
        return cls(
            window_title=cam_cfg.get("scrcpy_window_title", "ExtinguisherCam"),
            phone_ip=phone_ip or cam_cfg.get("phone_ip"),
            max_fps=cam_cfg.get("max_fps", 30),
            max_size=cam_cfg.get("max_size", 1280),
            video_bit_rate_mbps=cam_cfg.get("video_bit_rate_mbps", 8),
            no_audio=cam_cfg.get("no_audio", True),
            min_grab_interval_s=cam_cfg.get("min_grab_interval_s", 0.0),
        )

    def get_frame(self) -> npt.NDArray[np.uint8] | None:
        now = time.time()
        if self.min_grab_interval_s > 0 and now - self._last_grab_time < self.min_grab_interval_s:
            time.sleep(self.min_grab_interval_s - (now - self._last_grab_time))

        if not self.window:
            windows = [w for w in gw.getWindowsWithTitle(self.window_title)]
            if not windows:
                return None
            self.window = windows[0]

        try:
            bbox = {
                "top": self.window.top,
                "left": self.window.left,
                "width": self.window.width,
                "height": self.window.height,
            }
        except Exception:
            self.window = None
            return None

        if bbox["width"] <= 0 or bbox["height"] <= 0:
            return None

        sct_img = self.sct.grab(bbox)
        self._last_grab_time = time.time()
        frame = np.array(sct_img)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def cleanup(self) -> None:
        if self.scrcpy_proc:
            self.scrcpy_proc.terminate()
            self.scrcpy_proc.wait()
