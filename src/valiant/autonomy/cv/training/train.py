"""Train dry/shot YOLO models from synthetic or labelled data.

Requires labelled dataset in YOLO format under data/training/yolo/:

    data/training/yolo/
      images/train/
      images/val/
      labels/train/
      labels/val/
      data.yaml

Run after generate_targets.py has produced raw images, or after manual labelling.

Usage:
    python -m valiant.autonomy.cv.training.train --epochs 50
"""

from __future__ import annotations

import argparse
from pathlib import Path

from valiant.common.config import repo_root

DEFAULT_DATA_YAML = repo_root() / "data" / "training" / "yolo" / "data.yaml"


def train(
    data_yaml: Path,
    *,
    epochs: int = 50,
    imgsz: int = 224,
    output_name: str = "dry_shot",
) -> None:
    if not data_yaml.is_file():
        raise FileNotFoundError(
            f"Dataset config not found: {data_yaml}\n"
            "Create a YOLO data.yaml and labelled images first, or use HSV-only mode."
        )

    from ultralytics import YOLO

    model = YOLO("yolov8n.pt")
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        project=str(repo_root() / "models" / "runs"),
        name=output_name,
    )
    print(f"Training complete: {results}")
    print("Export ONNX: yolo export model=<best.pt> format=onnx")
    print("Copy exported models to models/dry.onnx and models/shot.onnx")


def main() -> None:
    parser = argparse.ArgumentParser(description="Train YOLO dry/shot detectors")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_YAML)
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--imgsz", type=int, default=224)
    parser.add_argument("--name", default="dry_shot")
    args = parser.parse_args()
    train(args.data, epochs=args.epochs, imgsz=args.imgsz, output_name=args.name)


if __name__ == "__main__":
    main()
