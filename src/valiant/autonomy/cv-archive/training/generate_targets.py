"""Generate synthetic dry (purple) and shot (blue) training images."""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
import numpy as np

from valiant.common.config import repo_root

# BGR colours approximating competition targets on white backing
DRY_BGR = (180, 60, 180)   # purple paper
SHOT_BGR = (200, 120, 40)  # blue after wetting (camera-dependent; tune in field)
WHITE_BGR = (255, 255, 255)


def _draw_target(
    canvas: np.ndarray,
    color: tuple[int, int, int],
    *,
    radius_range: tuple[int, int] = (25, 55),
) -> np.ndarray:
    h, w = canvas.shape[:2]
    margin = 80
    cx = random.randint(margin, w - margin)
    cy = random.randint(margin, h - margin)
    radius = random.randint(*radius_range)
    cv2.circle(canvas, (cx, cy), radius, color, thickness=-1)
    return canvas


def generate_dataset(
    output_dir: Path,
    *,
    count_per_class: int = 50,
    width: int = 1280,
    height: int = 720,
) -> None:
    dry_dir = output_dir / "dry"
    shot_dir = output_dir / "shot"
    dry_dir.mkdir(parents=True, exist_ok=True)
    shot_dir.mkdir(parents=True, exist_ok=True)

    for i in range(count_per_class):
        dry_img = np.full((height, width, 3), WHITE_BGR, dtype=np.uint8)
        _draw_target(dry_img, DRY_BGR)
        cv2.imwrite(str(dry_dir / f"dry_{i:04d}.jpg"), dry_img)

        shot_img = np.full((height, width, 3), WHITE_BGR, dtype=np.uint8)
        _draw_target(shot_img, SHOT_BGR)
        cv2.imwrite(str(shot_dir / f"shot_{i:04d}.jpg"), shot_img)

    print(f"Generated {count_per_class} dry + {count_per_class} shot images in {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic AEAC target images")
    parser.add_argument(
        "--output",
        type=Path,
        default=repo_root() / "data" / "training" / "targets",
    )
    parser.add_argument("--count", type=int, default=50)
    args = parser.parse_args()
    generate_dataset(args.output, count_per_class=args.count)


if __name__ == "__main__":
    main()
