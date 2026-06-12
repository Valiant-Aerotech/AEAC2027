#!/usr/bin/env python3
"""Verify Python environment and optional external tools."""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path


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
    root = Path(__file__).resolve().parents[1]
    expected = [
        "missions/task2_vion_auto_extinguish.py",
        "hardware/vion/rpi/run_mission.py",
        "hardware/vion/rpi/first_connect.sh",
        "hardware/vion/rpi/run_bringup_tests.sh",
        "hardware/vion/rpi/preflight_indoor.sh",
        "src/valiant/autonomy/orchestrator.py",
        "config/vion.yaml",
        "config/vion_calibration.yaml.example",
        "docs/runbooks/vion-bringup.md",
        "hardware/vion/mission-planner/002-pi-telem-params.md",
        "tools/bringup_gcs.ps1",
        "tools/check_mavlink_gcs.py",
        "tools/test_spray_gcs.py",
        "tools/run_calibration_pipeline.ps1",
    ]
    for rel in expected:
        path = root / rel
        status = "OK" if path.exists() else "MISSING"
        print(f"  {status}  [PATH] {rel}")


def main() -> int:
    print("=== Valiant Aerotech Environment Check ===\n")

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
        print(f"valiant package: OK (version {valiant.__version__})")
    except ImportError:
        print("valiant package: FAIL - run .\\tools\\setup.ps1")
        failures.append("valiant (pip install -e .)")

    if failures:
        print(f"\nFAILED - install missing packages and re-run setup.ps1")
        return 1

    print("\nPASSED - environment ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())
