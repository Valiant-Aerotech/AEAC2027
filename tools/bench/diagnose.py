#!/usr/bin/env python3
"""One-command environment diagnostic (Windows GCS + WSL SITL)."""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _line(ok: bool, name: str, fix: str = "") -> bool:
    tag = "OK  " if ok else "FAIL"
    print(f"  [{tag}] {name}")
    if not ok and fix:
        print(f"         fix: {fix}")
    return ok


def _wsl_ok(shell_cmd: str) -> tuple[bool, str]:
    if not shutil.which("wsl"):
        return False, "wsl not on PATH"
    try:
        proc = subprocess.run(
            ["wsl", "bash", "-lc", shell_cmd],
            capture_output=True,
            text=True,
            timeout=45,
        )
        out = (proc.stdout or proc.stderr or "").strip()
        return proc.returncode == 0, out
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except OSError as exc:
        return False, str(exc)


def main() -> int:
    print("=== Valiant diagnose ===\n")
    all_ok = True

    print("Windows / repo")
    _line(True, f"repo root: {ROOT}")
    all_ok &= _line(ROOT.joinpath("START_HERE.md").is_file(), "START_HERE.md")
    all_ok &= _line(
        ROOT.joinpath("tools/valiant.py").is_file(),
        "tools/valiant.py",
    )
    all_ok &= _line(
        ROOT.joinpath("tools/lib/diagnostics.ps1").is_file(),
        "tools/lib/diagnostics.ps1",
    )

    venv_py = ROOT / ".venv" / "Scripts" / "python.exe"
    has_venv = venv_py.is_file()
    all_ok &= _line(has_venv, ".venv Python", r".\start.ps1  or  .\tools\setup.ps1")

    py = str(venv_py) if has_venv else sys.executable
    try:
        ver = subprocess.check_output([py, "--version"], text=True).strip()
        _line(True, f"Python: {ver}")
    except (subprocess.CalledProcessError, OSError) as exc:
        all_ok &= _line(False, "Python runnable", str(exc))

    print("\nPython packages (required for GCS)")
    for module, pip_name in (
        ("numpy", "numpy"),
        ("cv2", "opencv-python"),
        ("pymavlink", "pymavlink"),
        ("yaml", "PyYAML"),
    ):
        try:
            importlib.import_module(module)
            _line(True, module)
        except ImportError:
            all_ok &= _line(False, module, f"pip install {pip_name}")

    print("\nWSL / SITL")
    wsl_path = shutil.which("wsl")
    all_ok &= _line(wsl_path is not None, "wsl on PATH", "wsl --install -d Ubuntu")

    if wsl_path:
        ok, out = _wsl_ok("wsl -l -q 2>/dev/null | head -1")
        distro = out.splitlines()[0].strip() if ok and out else "Ubuntu"
        _line(ok, f"WSL distro list ({distro or 'none'})")

        checks = (
            (
                "WSL script runner",
                "test -x ~/.valiant/bin/wsl_run.sh",
                r".\tools\setup_wsl.ps1",
            ),
            ("~/ardupilot clone", "test -d ~/ardupilot/.git", r".\tools\setup_wsl.ps1"),
            (
                "arducopter binary",
                "test -x ~/ardupilot/build/sitl/bin/arducopter",
                "Re-run .\\tools\\setup_wsl.ps1 or waf copter in Ubuntu",
            ),
            (
                "venv-ardupilot",
                "test -f ~/venv-ardupilot/bin/activate",
                "ArduPilot install-prereqs (setup_wsl step 3)",
            ),
            (
                "empy import",
                "python3 -c 'import empy'",
                "sudo apt install -y python3-empy  (in Ubuntu)",
            ),
        )
        for label, cmd, fix in checks:
            ok, _ = _wsl_ok(cmd)
            if label.startswith("arducopter") or label.startswith("WSL script"):
                all_ok &= _line(ok, label, fix)
            else:
                _line(ok, label, fix if not ok else "")

        print("\nWSL logs (last lines)")
        for log_path in (
            "~/.valiant_sitl_setup.log",
            "~/.valiant_sitl_build.log",
            "~/.valiant_wsl_last.log",
        ):
            ok, out = _wsl_ok(f"tail -3 {log_path} 2>/dev/null")
            print(f"  {log_path}:")
            if ok and out:
                for ln in out.splitlines():
                    print(f"    {ln}")
                if "BASH_SOURCE[0]" in out:
                    print(
                        "    (stale log from old launcher - re-run .\\tools\\launch_sitl.ps1 after git pull)"
                    )
            else:
                print("    (empty or missing)")

    print("\nDocs")
    for doc in (
        "docs/runbooks/sitl-wsl.md",
        "docs/runbooks/sitl-overview.md",
        "docs/runbooks/field-test-plan.md",
    ):
        _line(ROOT.joinpath(doc).is_file(), doc)

    print("\nSITL GCS STATUSTEXT")
    _line(
        ROOT.joinpath("tools/gcs/verify_sitl_statustext.py").is_file(),
        "verify_sitl_statustext.py",
    )
    print("  With SITL running + MP on tcp:127.0.0.1:5762:")
    print("    python tools\\valiant.py gcs verify-statustext")
    print("  Expect T2: VERIFY in Mission Planner Messages (sysid 1 when mp_use_autopilot_sysid)")

    print()
    if all_ok:
        print("All critical checks passed.")
        print("Next: .\\tools\\launch_sitl.ps1  then  python tools\\valiant.py sitl mission")
        return 0

    print("Some checks failed. See fix hints above.")
    print("Detailed WSL help: docs/runbooks/sitl-wsl.md")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
