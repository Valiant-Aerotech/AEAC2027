#!/usr/bin/env python3
"""Unified Valiant AEAC2027 tooling CLI.

Run with no arguments to see the scenario guide.
First time on a laptop: .\\start.ps1  or  python tools\\valiant.py setup
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent
_LIB = TOOLS / "lib"
sys.path.insert(0, str(_LIB))

from cli_diag import error, unexpected  # noqa: E402
from guide_text import GUIDE, QUICKSTART_NEXT  # noqa: E402


def _run(rel_path: str, argv: list[str] | None = None) -> int:
    """Run a tools script without tools/valiant.py shadowing the package."""
    src = str(ROOT / "src")
    script = str(TOOLS / rel_path)
    extra_argv = argv or []
    bootstrap = (
        "import runpy, sys\n"
        f"sys.path.insert(0, {src!r})\n"
        f"sys.argv = [{script!r}] + {extra_argv!r}\n"
        f"raise SystemExit(runpy.run_path({script!r}, run_name='__main__') or 0)\n"
    )
    return subprocess.call([sys.executable, "-c", bootstrap], cwd=str(ROOT))


def cmd_guide(_: argparse.Namespace) -> int:
    print(GUIDE.strip())
    return 0


def cmd_quickstart(_: argparse.Namespace) -> int:
    print("=== Valiant quickstart ===\n")
    steps = (
        ("Environment", cmd_env_check),
        ("Flight boundary", cmd_boundary_check),
        ("Safety logic", cmd_bench_safety),
    )
    failed = False
    for label, fn in steps:
        print(f"--- {label} ---")
        rc = fn(argparse.Namespace())
        if rc != 0:
            failed = True
            print(f"FAIL: {label}\n")
        else:
            print(f"OK: {label}\n")
    print(QUICKSTART_NEXT.strip())
    return 1 if failed else 0


def cmd_setup(_: argparse.Namespace) -> int:
    ps1 = TOOLS / "setup.ps1"
    if not ps1.exists():
        return error(f"{ps1} not found", "Re-clone the repo")
    return subprocess.call(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
        cwd=str(ROOT),
    )


def cmd_bench_smoke(_: argparse.Namespace) -> int:
    return cmd_quickstart(_)


def cmd_env_check(_: argparse.Namespace) -> int:
    return _run("bench/verify_env.py")


def cmd_diagnose(_: argparse.Namespace) -> int:
    return _run("bench/diagnose.py")


BOUNDARY_POLY = ROOT / "config" / "aeac2027_boundary.poly"


def _boundary_module():
    """Import the boundary module without tools/valiant.py shadowing the package."""
    sys.path.insert(0, str(ROOT / "src"))
    from valiant.core.safety import boundary

    return boundary


def cmd_boundary_export(_: argparse.Namespace) -> int:
    """Write the Appendix C polygon for Mission Planner to load."""
    b = _boundary_module()
    out = b.write_polygon_file(BOUNDARY_POLY)
    print(f"Wrote {out.relative_to(ROOT)} ({len(b.HARD_BOUNDARY)} vertices)\n")
    print("Load it in Mission Planner:")
    print("  1. Plan screen, FENCE in the dropdown at top right")
    print("  2. Polygon tool, Load Polygon, pick this file")
    print("  3. Polygon tool again, Fence Inclusion")
    print("  4. Write")
    print("\nThe link must be MAVLink2 to upload a fence. USB already is.")
    return 0


def cmd_boundary_check(_: argparse.Namespace) -> int:
    """Confirm the committed polygon file still matches the coded constants."""
    b = _boundary_module()
    lat_min, lon_min, lat_max, lon_max = b.polygon_bounds()
    centre = b.polygon_centroid()
    print(f"Vertices:  {len(b.HARD_BOUNDARY)}")
    print(f"Latitude:  {lat_min:.7f} .. {lat_max:.7f}")
    print(f"Longitude: {lon_min:.7f} .. {lon_max:.7f}")
    print(f"Centroid:  {centre[0]:.7f}, {centre[1]:.7f}")
    print(f"Ceiling:   {b.MAX_ALTITUDE_AGL_M:.0f} m AGL")
    print(f"Soft inset: {b.DEFAULT_SOFT_INSET_M:.0f} m (our value, not the CONOPS - see docs)")

    if not BOUNDARY_POLY.exists():
        error(f"{BOUNDARY_POLY.name} is missing. Run: valiant boundary export")
        return 1

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        fresh = b.write_polygon_file(Path(tmp) / "check.poly")
        if fresh.read_text(encoding="utf-8") != BOUNDARY_POLY.read_text(encoding="utf-8"):
            error(
                f"{BOUNDARY_POLY.name} does not match the coded boundary. "
                "Run: valiant boundary export"
            )
            return 1
    print(f"\nOK: {BOUNDARY_POLY.name} matches the coded boundary.")
    return 0


def cmd_gcs_heartbeat(args: argparse.Namespace) -> int:
    return _run("gcs/check_mavlink_gcs.py", args.extra)


def cmd_gcs_monitor(args: argparse.Namespace) -> int:
    return _run("gcs/mission_monitor.py", args.extra)


def cmd_gcs_verify_statustext(args: argparse.Namespace) -> int:
    return _run("gcs/verify_sitl_statustext.py", args.extra)


def cmd_gcs_params(args: argparse.Namespace) -> int:
    argv = list(args.extra or [])
    if args.connection:
        argv.extend(["--connection", args.connection])
    return _run("gcs/read_fc_params.py", argv)


def cmd_gcs_listen(args: argparse.Namespace) -> int:
    return _run("gcs/mavproxy_listen.py", args.extra)


def cmd_sitl_map_download(args: argparse.Namespace) -> int:
    return _run("sitl/download_sitl_map.py", args.extra)


def cmd_bench_cv(args: argparse.Namespace) -> int:
    argv = list(args.extra or [])
    if args.regression:
        argv = ["--regression", *argv]
    return _run("bench/cv_bench_test.py", argv)


def cmd_bench_metric(args: argparse.Namespace) -> int:
    return _run("bench/metric_bench_test.py", args.extra)


def cmd_bench_safety(_: argparse.Namespace) -> int:
    return _run("bench/safety_bench_test.py")


def cmd_calibrate_tune(args: argparse.Namespace) -> int:
    return _run("calibrate/calibrate_depth_rgb.py", args.extra)


def cmd_calibrate_validate(args: argparse.Namespace) -> int:
    return _run("calibrate/validate_calibration.py", args.extra)


def cmd_calibrate_replay(args: argparse.Namespace) -> int:
    return _run("calibrate/replay_rpi_recording.py", args.extra)


def cmd_bringup_phase1(args: argparse.Namespace) -> int:
    ps1 = TOOLS / "bringup" / "phase1_bringup.ps1"
    extra: list[str] = []
    if getattr(args, "skip_mavlink", False):
        extra.append("-SkipMavlink")
    return subprocess.call(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), *extra],
        cwd=str(ROOT),
    )


def cmd_bringup_phase1_pi(_: argparse.Namespace) -> int:
    sh = ROOT / "hardware" / "vion" / "rpi" / "phase1_bringup.sh"
    return subprocess.call(["bash", str(sh)], cwd=str(ROOT))


def cmd_sitl_setup_wsl(_: argparse.Namespace) -> int:
    ps1 = TOOLS / "setup_wsl.ps1"
    if not ps1.exists():
        return error(f"{ps1} not found", r"Run from repo root")
    return subprocess.call(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
        cwd=str(ROOT),
    )


def cmd_sitl_test(_: argparse.Namespace) -> int:
    ps1 = TOOLS / "sitl" / "run_sitl_tests.ps1"
    if ps1.exists():
        return subprocess.call(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
            cwd=str(ROOT),
        )
    return subprocess.call(
        [sys.executable, "-m", "pytest", "tests/sitl", "tests/test_sitl_motion.py", "-q"],
        cwd=str(ROOT),
    )


def cmd_sitl_mission(args: argparse.Namespace) -> int:
    ps1 = TOOLS / "run_sitl_mission.ps1"
    extra = args.extra or []
    if ps1.exists() and not extra:
        return subprocess.call(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)],
            cwd=str(ROOT),
        )
    return subprocess.call(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), *extra],
        cwd=str(ROOT),
    )


def cmd_sitl_run(args: argparse.Namespace) -> int:
    ps1 = TOOLS / "run_sitl_mission_file.ps1"
    mission = args.mission_file
    extra: list[str] = ["-Mission", mission]
    if args.headless:
        extra.append("-Headless")
    if args.skip_preflight:
        extra.append("-SkipPreflight")
    if args.no_monitor:
        extra.append("-NoMonitor")
    return subprocess.call(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), *extra],
        cwd=str(ROOT),
    )


def cmd_sitl_pattern(args: argparse.Namespace) -> int:
    ps1 = TOOLS / "run_sitl_pattern.ps1"
    extra: list[str] = []
    if args.skip_preflight:
        extra.append("-SkipPreflight")
    if args.no_monitor:
        extra.append("-NoMonitor")
    if ps1.exists() and not args.extra:
        return subprocess.call(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), *extra],
            cwd=str(ROOT),
        )
    argv = list(args.extra or [])
    if args.skip_preflight:
        argv.append("--skip-preflight")
    return _run("sitl/sitl_pattern_flight.py", argv)


def cmd_sitl_orbit(args: argparse.Namespace) -> int:
    ps1 = TOOLS / "run_sitl_orbit.ps1"
    extra: list[str] = []
    if args.skip_preflight:
        extra.append("-SkipPreflight")
    if args.no_monitor:
        extra.append("-NoMonitor")
    if args.laps is not None:
        extra.extend(["-Laps", str(args.laps)])
    if ps1.exists() and not args.extra:
        return subprocess.call(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1), *extra],
            cwd=str(ROOT),
        )
    argv = list(args.extra or [])
    if args.skip_preflight:
        argv.append("--skip-preflight")
    if args.laps is not None:
        argv.extend(["--laps", str(args.laps)])
    return _run("sitl/sitl_orbit_flight.py", argv)


def cmd_field_orbit(args: argparse.Namespace) -> int:
    argv = list(args.extra or [])
    if args.profile:
        argv.extend(["--profile", args.profile])
    if args.connection:
        argv.extend(["--connection", args.connection])
    if args.gcs_ip:
        argv.extend(["--gcs-ip", args.gcs_ip])
    if args.laps is not None:
        argv.extend(["--laps", str(args.laps)])
    return _run("field/run_field_orbit.py", argv)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="valiant",
        description="Valiant AEAC2027 - one CLI for setup, bench, SITL, and bringup",
        epilog="First time? Run: python tools/valiant.py guide  or read START_HERE.md",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=False)

    sub.add_parser(
        "guide",
        help="Show scenario picker (what should I run?)",
    ).set_defaults(func=cmd_guide)
    sub.add_parser(
        "diagnose",
        help="Check Windows venv, WSL SITL, and common failure points",
    ).set_defaults(func=cmd_diagnose)
    sub.add_parser(
        "quickstart",
        help="Run env + CONOPS + safety checks, then show next steps",
    ).set_defaults(func=cmd_quickstart)
    sub.add_parser(
        "setup",
        help="One-time Windows setup (venv + pip install)",
    ).set_defaults(func=cmd_setup)

    p = sub.add_parser("env", help="Environment checks")
    s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("check", help="Verify Python packages and tools").set_defaults(
        func=cmd_env_check
    )

    p = sub.add_parser("boundary", help="Competition flight boundary (CONOPS Appendix C)")
    s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("export", help="Write the polygon file for Mission Planner").set_defaults(
        func=cmd_boundary_export
    )
    s.add_parser("check", help="Verify the polygon file matches the coded boundary").set_defaults(
        func=cmd_boundary_check
    )

    p = sub.add_parser("gcs", help="Ground control station tools")
    s = p.add_subparsers(dest="sub", required=True)
    for name, fn, help_text in (
        ("heartbeat", cmd_gcs_heartbeat, "Check the MAVLink link to the aircraft"),
        ("monitor", cmd_gcs_monitor, "Watch companion telemetry"),
        ("listen", cmd_gcs_listen, "Print incoming MAVLink messages"),
        ("verify-statustext", cmd_gcs_verify_statustext, "Check STATUSTEXT reaches the GCS"),
        ("params", cmd_gcs_params, "Read back FC safety parameters (advisory)"),
    ):
        sp = s.add_parser(name, help=help_text)
        if name == "params":
            sp.add_argument("--connection", default=None)
        sp.add_argument("extra", nargs=argparse.REMAINDER)
        sp.set_defaults(func=fn)

    p = sub.add_parser("sitl", help="Software-in-the-loop")
    s = p.add_subparsers(dest="sub", required=True)
    sp = s.add_parser("setup-wsl", help="One-time WSL + ArduPilot install (fresh PC)")
    sp.set_defaults(func=cmd_sitl_setup_wsl)
    sp = s.add_parser("test", help="Run SITL pytest suite")
    sp.set_defaults(func=cmd_sitl_test)
    sp = s.add_parser("mission", help="Run Task 2 SITL mission")
    sp.add_argument("extra", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_sitl_mission)
    sp = s.add_parser("run", help="Run SITL mission from YAML config file")
    sp.add_argument("mission_file", help="Path to config/sitl_missions/*.yaml")
    sp.add_argument("--headless", action="store_true")
    sp.add_argument("--skip-preflight", action="store_true")
    sp.add_argument("--no-monitor", action="store_true")
    sp.set_defaults(func=cmd_sitl_run)
    sp = s.add_parser("pattern", help="Guided box pattern then LOITER (no CV mission)")
    sp.add_argument("--skip-preflight", action="store_true")
    sp.add_argument("--no-monitor", action="store_true")
    sp.add_argument("extra", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_sitl_pattern)
    sp = s.add_parser("orbit", help="Guided orbit then LOITER (field geometry, SITL first)")
    sp.add_argument("--skip-preflight", action="store_true")
    sp.add_argument("--no-monitor", action="store_true")
    sp.add_argument("--laps", type=int, default=None, help="Override lap count")
    sp.add_argument("extra", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_sitl_orbit)
    sp = s.add_parser("map", help="SITL map assets")
    sm = sp.add_subparsers(dest="map_cmd", required=True)
    sp2 = sm.add_parser("download", help="Download satellite tiles")
    sp2.add_argument("extra", nargs=argparse.REMAINDER)
    sp2.set_defaults(func=cmd_sitl_map_download)

    p = sub.add_parser("bench", help="Bench and regression tests")
    s = p.add_subparsers(dest="sub", required=True)
    sp = s.add_parser("cv", help="CV detection bench")
    sp.add_argument("--regression", action="store_true")
    sp.add_argument("extra", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_bench_cv)
    sp = s.add_parser("metric", help="CV + metric recon bench")
    sp.add_argument("extra", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_bench_metric)
    sp = s.add_parser("safety", help="Safety monitor unit tests")
    sp.set_defaults(func=cmd_bench_safety)
    sp = s.add_parser("smoke", help="Same as quickstart (env + CONOPS + safety)")
    sp.set_defaults(func=cmd_bench_smoke)

    p = sub.add_parser("calibrate", help="RGB/depth calibration")
    s = p.add_subparsers(dest="sub", required=True)
    for name, fn in (
        ("tune", cmd_calibrate_tune),
        ("validate", cmd_calibrate_validate),
        ("replay", cmd_calibrate_replay),
    ):
        sp = s.add_parser(name)
        sp.add_argument("extra", nargs=argparse.REMAINDER)
        sp.set_defaults(func=fn)

    p = sub.add_parser("bringup", help="Hardware bringup checklists")
    s = p.add_subparsers(dest="sub", required=True)
    sp = s.add_parser("phase1", help="Phase 1 GCS checks (field-test-plan)")
    sp.add_argument(
        "--skip-mavlink",
        action="store_true",
        help="Skip MAVLink heartbeat (laptop-only)",
    )
    sp.set_defaults(func=cmd_bringup_phase1)
    sp = s.add_parser("phase1-pi", help="Phase 1 Pi checks (run on companion)")
    sp.set_defaults(func=cmd_bringup_phase1_pi)

    p = sub.add_parser("field", help="Field flight scripts (no CV orchestrator)")
    s = p.add_subparsers(dest="sub", required=True)
    sp = s.add_parser("orbit", help="GUIDED-triggered orbit on Pi UART")
    sp.add_argument("--profile", default="vivi_orbit")
    sp.add_argument("--connection", default=None)
    sp.add_argument("--gcs-ip", default=None)
    sp.add_argument("--laps", type=int, default=None, help="Override lap count")
    sp.add_argument("extra", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_field_orbit)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        if args.command is None:
            return cmd_guide(args)
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except SystemExit as exc:
        code = exc.code
        if code is None:
            return 0
        if isinstance(code, int):
            return code
        return 1
    except Exception as exc:
        try:
            from valiant.core.errors import ValiantError
        except ImportError:
            return unexpected(exc)
        if isinstance(exc, ValiantError):
            print(f"ERROR: {exc.detail}", file=sys.stderr)
            return 1
        return unexpected(exc)


if __name__ == "__main__":
    raise SystemExit(main())
