#!/usr/bin/env python3
"""Verify Python environment and 2027 repo layout."""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_IMPORTS = [
    ("numpy", "numpy"),
    ("cv2", "opencv-python"),
    ("pymavlink", "pymavlink"),
    ("yaml", "PyYAML"),
]

OPTIONAL_IMPORTS = [
    ("mss", "mss"),
    ("pygetwindow", "pygetwindow"),
    ("onnxruntime", "onnxruntime"),
    ("ultralytics", "ultralytics"),
    ("valiant_mav", "valiant-mav (pip install -e ../valiant-mav)"),
]

EXTERNAL_TOOLS = [
    ("scrcpy", "scrcpy (phone camera mirror)"),
    ("adb", "adb (Android debug)"),
]


def check_imports(packages: list[tuple[str, str]], required: bool) -> list[str]:
    failures = []
    label = "REQUIRED" if required else "OPTIONAL"
    for module, pip_name in packages:
        try:
            importlib.import_module(module)
            print(f"  OK  [{label}] {module}")
        except ImportError:
            print(f"  FAIL [{label}] {module} - pip install {pip_name}")
            if required:
                failures.append(pip_name)
    return failures


def check_external() -> None:
    for cmd, desc in EXTERNAL_TOOLS:
        path = shutil.which(cmd)
        if path:
            print(f"  OK  [TOOL] {desc}: {path}")
        else:
            print(f"  WARN [TOOL] {desc} not on PATH")


def check_structure() -> None:
    expected = [
        "START_HERE.md",
        "start.ps1",
        "tools/valiant.py",
        "tools/lib/guide_text.py",
        "tools/bench/verify_env.py",
        "tools/bench/diagnose.py",
        "tools/sitl/launch_sitl.sh",
        "tools/sitl/sitl_orbit_flight.py",
        "tools/sitl/sitl_pattern_flight.py",
        "tools/field/run_field_orbit.py",
        "config/defaults.yaml",
        "config/aeac2027_boundary.poly",
        "config/sitl_missions/orbit.yaml",
        "config/sitl_missions/pattern_box.yaml",
        "src/valiant/missions/survey/course.py",
        "src/valiant/missions/survey/cluster.py",
        "src/valiant/missions/tagtrack/__init__.py",
        "src/valiant/comms/competition/client.py",
        "src/valiant/core/safety/boundary.py",
        "hardware/vion/lua/safety.lua",
        "docs/conops-2027.md",
        "docs/lessons-learned.md",
        "reference/topics.md",
        ".env.example",
    ]
    for rel in expected:
        path = REPO_ROOT / rel
        status = "OK" if path.exists() else "MISSING"
        print(f"  {status}  [PATH] {rel}")


def main() -> int:
    print("=== Valiant Aerotech Environment Check (AEAC 2027) ===\n")

    print(f"Python: {sys.version}")
    print(f"Executable: {sys.executable}\n")

    print("Python packages:")
    failures = check_imports(REQUIRED_IMPORTS, required=True)
    check_imports(OPTIONAL_IMPORTS, required=False)
    print()

    print("External tools:")
    check_external()
    print()

    print("Repo structure:")
    check_structure()
    print()

    try:
        import valiant

        print(f"valiant package: OK (version {getattr(valiant, '__version__', '?')})")
    except ImportError:
        print("valiant package: FAIL - run .\\tools\\setup.ps1 or pip install -e .")
        failures.append("aeac2027")

    mav_root = REPO_ROOT.parent / "valiant-mav"
    if mav_root.is_dir():
        print(f"valiant-mav sibling: OK ({mav_root})")
    else:
        print(f"valiant-mav sibling: WARN not found at {mav_root}")

    print()
    if failures:
        print(f"FAILED: install {', '.join(failures)}")
        return 1
    print("Environment check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
