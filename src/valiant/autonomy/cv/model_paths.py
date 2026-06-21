"""Resolve CV model paths from config."""

from __future__ import annotations

from pathlib import Path

from valiant.common.config import repo_root


def resolve_dry_model_path(cfg: dict) -> Path | None:
    cv_cfg = cfg.get("cv", {})
    model_rel = cv_cfg.get("models", {}).get("dry", "models/dry.onnx")
    candidates = [
        repo_root() / model_rel,
        repo_root() / "models" / "dry.onnx",
        repo_root() / "models" / "dry.pt",
        repo_root() / "models" / "best.onnx",
        repo_root() / "models" / "best.pt",
    ]
    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.is_file():
            return candidate
    return None


def resolve_shot_model_path(cfg: dict) -> Path | None:
    cv_cfg = cfg.get("cv", {})
    model_rel = cv_cfg.get("models", {}).get("shot", "models/shot.onnx")
    candidates = [
        repo_root() / model_rel,
        repo_root() / "models" / "shot.onnx",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None
