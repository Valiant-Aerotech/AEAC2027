"""Subsystem import boundary checks."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_CV_PREFIXES = (
    "valiant.autonomy.cv.subframe_",
    "valiant.autonomy.cv.yolo_onnx",
    "valiant.autonomy.cv.dry_detector",
    "valiant.autonomy.cv.model_paths",
    "valiant.autonomy.cv.shot_detector",
    "valiant.autonomy.cv.hsv",
)

ALLOWED_CV_MODULES = {
    "valiant.autonomy.cv",
    "valiant.autonomy.cv.exceptions",
    "valiant.autonomy.cv.api",
}

MODULES_TO_CHECK = [
    REPO_ROOT / "src" / "valiant" / "autonomy" / "orchestrator.py",
    REPO_ROOT / "src" / "valiant" / "autonomy" / "metric_recon" / "reconstructor.py",
    REPO_ROOT / "src" / "valiant" / "autonomy" / "auto_nav" / "planner.py",
]


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_upstream_modules_avoid_cv_internals():
    violations: list[str] = []
    for path in MODULES_TO_CHECK:
        for mod in _imported_modules(path):
            if any(mod.startswith(p) for p in FORBIDDEN_CV_PREFIXES):
                violations.append(f"{path.name} imports forbidden {mod}")
            if mod.startswith("valiant.autonomy.cv.") and mod not in ALLOWED_CV_MODULES:
                if mod == "valiant.autonomy.cv.detector":
                    violations.append(f"{path.name} imports internal {mod} (use valiant.autonomy.cv)")
                elif mod == "valiant.autonomy.cv.ui":
                    violations.append(f"{path.name} imports internal {mod} (use draw_mission_overlay)")
    assert not violations, "\n".join(violations)


def test_metric_recon_imports_no_cv():
    path = REPO_ROOT / "src" / "valiant" / "autonomy" / "metric_recon" / "reconstructor.py"
    for mod in _imported_modules(path):
        assert not mod.startswith("valiant.autonomy.cv"), f"metric recon imports {mod}"
