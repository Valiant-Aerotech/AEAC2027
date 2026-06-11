"""Manual Task 2 photo capture - operator-flown fallback."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import csv
import cv2


def capture_task2_photos(
    team_name: str,
    camera_index: int = 0,
    output_dir: str = "task2_photos",
) -> None:
    """Save photos when operator presses ENTER after manually extinguishing a target."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    log_file = output_path / "task2_photo_log.csv"

    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {camera_index}")

    target_number = 1

    if not log_file.exists():
        with open(log_file, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(["target_number", "filename", "timestamp"])

    print("Task Two manual photo capture started.")
    print("Press ENTER in the camera window to save a photo. Press Q to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
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
            filename = f"Task_2_{team_name}_target_{target_number}.jpg"
            filepath = output_path / filename
            cv2.imwrite(str(filepath), frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            with open(log_file, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow([target_number, filename, timestamp])
            print(f"Saved: {filepath}")
            target_number += 1
        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
