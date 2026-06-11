"""Manual Task 2 photo capture - operator-flown fallback."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import time

import cv2

from valiant.autonomy.conops import task2_photo_filename
from valiant.autonomy.upload.drive import DriveUploader
from valiant.common.camera import ScrcpyCamera


class _FrameSource:
    def get_frame(self):
        raise NotImplementedError

    def cleanup(self) -> None:
        pass


class _WebcamSource(_FrameSource):
    def __init__(self, camera_index: int):
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open camera index {camera_index}")

    def get_frame(self):
        ret, frame = self.cap.read()
        return frame if ret else None

    def cleanup(self) -> None:
        self.cap.release()


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
        frame_source = _WebcamSource(camera_index)

    uploader = DriveUploader(cfg) if upload and cfg else None
    target_number = 1

    if not log_file.exists():
        with open(log_file, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["target_number", "filename", "timestamp", "uploaded"])

    print("Task Two manual photo capture started.")
    print("Press ENTER in the camera window to save a photo. Press Q to quit.")

    try:
        while True:
            frame = frame_source.get_frame()
            if frame is None:
                if source == "scrcpy":
                    time.sleep(0.5)
                continue

            display = frame.copy()
            cv2.putText(
                display,
                f"Next: Target {target_number} | ENTER=save | Q=quit",
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 255),
                2,
            )
            cv2.imshow("Task Two Manual Capture", display)
            key = cv2.waitKey(1) & 0xFF

            if key == 13:
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
            elif key == ord("q"):
                break
    finally:
        frame_source.cleanup()
        cv2.destroyAllWindows()
