#!/usr/bin/env python3
"""Unified Valiant AEAC2027 tooling CLI."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = Path(__file__).resolve().parent


def _run(module_main: str, argv: list[str] | None = None) -> int:
    cmd = [sys.executable, str(TOOLS / module_main), *(argv or [])]
    return subprocess.call(cmd, cwd=str(ROOT))


def cmd_env_check(_: argparse.Namespace) -> int:
    return _run("verify_env.py")


def cmd_conops_check(_: argparse.Namespace) -> int:
    return _run("conops_check.py")


def cmd_gcs_heartbeat(args: argparse.Namespace) -> int:
    return _run("check_mavlink_gcs.py", args.extra)


def cmd_gcs_spray(args: argparse.Namespace) -> int:
    return _run("test_spray_gcs.py", args.extra)


def cmd_gcs_monitor(args: argparse.Namespace) -> int:
    return _run("mission_monitor.py", args.extra)


def cmd_gcs_listen(args: argparse.Namespace) -> int:
    return _run("mavproxy_listen.py", args.extra)


def cmd_sitl_map_download(args: argparse.Namespace) -> int:
    return _run("download_sitl_map.py", args.extra)


def cmd_bench_cv(args: argparse.Namespace) -> int:
    argv = list(args.extra or [])
    if args.regression:
        argv = ["--regression", *argv]
    return _run("cv_bench_test.py", argv)


def cmd_bench_metric(args: argparse.Namespace) -> int:
    return _run("metric_bench_test.py", args.extra)


def cmd_bench_safety(_: argparse.Namespace) -> int:
    return _run("safety_bench_test.py")


def cmd_calibrate_tune(args: argparse.Namespace) -> int:
    return _run("calibrate_depth_rgb.py", args.extra)


def cmd_calibrate_validate(args: argparse.Namespace) -> int:
    return _run("validate_calibration.py", args.extra)


def cmd_calibrate_replay(args: argparse.Namespace) -> int:
    return _run("replay_rpi_recording.py", args.extra)


def cmd_sitl_test(_: argparse.Namespace) -> int:
    ps1 = TOOLS / "run_sitl_tests.ps1"
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="valiant",
        description="Valiant AEAC2027 unified tooling",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("env", help="Environment checks")
    s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("check", help="Verify Python packages and tools").set_defaults(
        func=cmd_env_check
    )

    p = sub.add_parser("conops", help="CONOPS validation")
    s = p.add_subparsers(dest="sub", required=True)
    s.add_parser("check", help="Validate config against CONOPS").set_defaults(
        func=cmd_conops_check
    )

    p = sub.add_parser("gcs", help="Ground control station tools")
    s = p.add_subparsers(dest="sub", required=True)
    for name, fn in (
        ("heartbeat", cmd_gcs_heartbeat),
        ("spray", cmd_gcs_spray),
        ("monitor", cmd_gcs_monitor),
        ("listen", cmd_gcs_listen),
    ):
        sp = s.add_parser(name)
        sp.add_argument("extra", nargs=argparse.REMAINDER)
        sp.set_defaults(func=fn)

    p = sub.add_parser("sitl", help="Software-in-the-loop")
    s = p.add_subparsers(dest="sub", required=True)
    sp = s.add_parser("test", help="Run SITL pytest suite")
    sp.set_defaults(func=cmd_sitl_test)
    sp = s.add_parser("mission", help="Run Task 2 SITL mission")
    sp.add_argument("extra", nargs=argparse.REMAINDER)
    sp.set_defaults(func=cmd_sitl_mission)
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
