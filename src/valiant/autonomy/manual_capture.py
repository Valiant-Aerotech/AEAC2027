"""Manual Task 2 photo capture - operator-flown fallback."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import time

import cv2
import numpy as np

from valiant.autonomy.conops import task2_photo_filename
from valiant.autonomy.upload.drive import DriveUploader
from valiant.common.camera import ScrcpyCamera, WebcamCamera


class _FrameSource:
    def get_frame(self):
        raise NotImplementedError

    def cleanup(self) -> None:
        pass


class _ScrcpySource(_FrameSource):
    def __init__(self, cfg: dict, phone_ip: str | None = None):
        self.camera = ScrcpyCamera.from_config(cfg, phone_ip=phone_ip)

    def get_frame(self):
        return self.camera.get_frame()

    def cleanup(self) -> None:
        self.camera.cleanup()


def capture_task2_photos(
    team_name: str | None = None,
    *,
    source: str = "webcam",
    camera_index: int = 0,
    output_dir: str = "task2_photos",
    cfg: dict | None = None,
    phone_ip: str | None = None,
    upload: bool = False,
) -> None:
    """Save photos when operator presses ENTER after manually extinguishing a target."""
    if cfg is not None:
        cfg.setdefault("team", {})["name"] = team_name or cfg.get("team", {}).get("name", "ValiantAerotech")

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    log_file = output_path / "task2_photo_log.csv"

    if source == "scrcpy":
        if cfg is None:
            raise ValueError("cfg is required when source=scrcpy")
        frame_source: _FrameSource = _ScrcpySource(cfg, phone_ip=phone_ip)
        print("Using scrcpy window capture. Waiting for ExtinguisherCam...")
    else:
        frame_source = WebcamCamera(camera_index)

    uploader = DriveUploader(cfg) if upload and cfg else None
    target_number = 1

    if not log_file.exists():
        with open(log_file, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["target_number", "filename", "timestamp", "uploaded"])

    print("Task Two manual photo capture started.")
    print("Press ENTER in the OpenCV window to save a photo. Press Q or ESC to quit.")

    window_name = "Task Two Manual Capture"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    quit_keys = {ord("q"), ord("Q"), 27}

    try:
        while True:
            frame = frame_source.get_frame()
            if frame is None:
                display = np.zeros((480, 640, 3), dtype=np.uint8)
                status = "Waiting for camera feed..."
                if source == "scrcpy":
                    time.sleep(0.1)
            else:
                display = frame.copy()
                status = f"Next: Target {target_number} | ENTER=save | Q=quit"

            cv2.putText(
                display,
                status,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )
            cv2.imshow(window_name, display)
            key = cv2.waitKey(1) & 0xFF

            if key in quit_keys:
                print("Quit requested.")
                break

            if key == 13 and frame is not None:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                if cfg:
                    filename = task2_photo_filename(cfg, target_number)
                else:
                    name = team_name or "ValiantAerotech"
                    filename = f"Task_2_{name}_target_{target_number}.jpg"
                filepath = output_path / filename
                cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                uploaded = False
                if uploader:
                    uploaded = uploader.upload_task2_photo(str(filepath), target_number)
                with open(log_file, "a", newline="", encoding="utf-8") as f:
                    csv.writer(f).writerow([target_number, filename, timestamp, uploaded])
                print(f"Saved: {filepath}")
                target_number += 1
    finally:
        print("Cleaning up camera...")
        frame_source.cleanup()
        cv2.destroyWindow(window_name)
        cv2.destroyAllWindows()
        cv2.waitKey(1)
