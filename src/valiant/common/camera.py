"""scrcpy window capture for GCS-offload camera feed."""

from __future__ import annotations

import os
import subprocess
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
    ):
        if not HAVE_SCREEN_CAPTURE:
            raise RuntimeError(
                "mss and pygetwindow required. Run: pip install mss pygetwindow"
            )
        self.window_title = window_title
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

        try:
            self.scrcpy_proc = subprocess.Popen(
                ["scrcpy", "--stay-awake", f"--window-title={window_title}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=c_flags,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                "scrcpy not found on PATH. Install scrcpy before running Task 2."
            ) from exc

    def get_frame(self) -> npt.NDArray[np.uint8] | None:
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
        frame = np.array(sct_img)
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)

    def cleanup(self) -> None:
        if self.scrcpy_proc:
            self.scrcpy_proc.terminate()
            self.scrcpy_proc.wait()
