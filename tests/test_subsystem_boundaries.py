"""Subsystem import boundary checks."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_CV_PREFIXES = (
    "valiant.perception.detect.subframe_",
    "valiant.perception.detect.yolo_onnx",
    "valiant.perception.detect.dry_detector",
    "valiant.perception.detect.model_paths",
    "valiant.perception.detect.shot_detector",
    "valiant.perception.detect.hsv",
)

ALLOWED_CV_MODULES = {
    "valiant.perception.detect",
    "valiant.perception.detect.exceptions",
    "valiant.perception.detect.api",
}

ORCHESTRATOR_FORBIDDEN_PREFIXES = (
    "valiant.perception.metric_recon.reconstructor",
    "valiant.perception.metric_recon.edge_proximity",
    "valiant.perception.metric_recon.aim_offset",
    "valiant.perception.metric_recon.lateral_clearance",
    "valiant.perception.metric_recon.vertical_clearance",
    "valiant.perception.depth.map",
    "valiant.perception.geometry",
    "valiant.core.nav.driver",
    "valiant.core.nav.approach",
    "valiant.core.nav.visual_servo",
    "valiant.core.nav.approach_motion",
    "valiant.autonomy.spray.aim",
    "valiant.autonomy.spray.actuation",
)

ALLOWED_ORCHESTRATOR_MODULES = {
    "valiant.perception.metric_recon",
    "valiant.perception.metric_recon.api",
    "valiant.core.nav",
    "valiant.core.nav",
    "valiant.autonomy.spray",
    "valiant.autonomy.spray.api",
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
            if mod.startswith("valiant.perception.detect.") and mod not in ALLOWED_CV_MODULES:
                if mod == "valiant.perception.detect.detector":
                    violations.append(f"{path.name} imports internal {mod} (use valiant.perception.detect)")
                elif mod == "valiant.perception.detect.ui":
                    violations.append(f"{path.name} imports internal {mod} (use draw_mission_overlay)")
    assert not violations, "\n".join(violations)


def test_orchestrator_uses_public_subsystem_apis():
    path = REPO_ROOT / "src" / "valiant" / "autonomy" / "orchestrator.py"
    violations: list[str] = []
    for mod in _imported_modules(path):
        if any(mod.startswith(p) for p in ORCHESTRATOR_FORBIDDEN_PREFIXES):
            violations.append(f"orchestrator imports internal {mod}")
        for prefix in (
            "valiant.perception.metric_recon.",
            "valiant.core.nav.",
            "valiant.autonomy.spray.",
        ):
            if mod.startswith(prefix) and mod not in ALLOWED_ORCHESTRATOR_MODULES:
                violations.append(f"orchestrator imports internal {mod} (use package public API)")
    assert not violations, "\n".join(violations)


def test_metric_recon_imports_no_cv():
    path = REPO_ROOT / "src" / "valiant" / "autonomy" / "metric_recon" / "reconstructor.py"
    for mod in _imported_modules(path):
        assert not mod.startswith("valiant.perception.detect"), f"metric recon imports {mod}"


def test_auto_nav_planner_imports_spray_public_api():
    path = REPO_ROOT / "src" / "valiant" / "autonomy" / "auto_nav" / "planner.py"
    for mod in _imported_modules(path):
        if mod.startswith("valiant.autonomy.spray.") and mod not in {
            "valiant.autonomy.spray",
            "valiant.autonomy.spray.api",
        }:
            raise AssertionError(f"planner imports internal {mod} (use valiant.autonomy.spray)")
