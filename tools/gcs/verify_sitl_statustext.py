#!/usr/bin/env python3
"""Send a test T2: STATUSTEXT and optionally sniff Mission Planner's SITL port."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from valiant.common.config import load_config
from valiant.common.mavlink import (
    GcsStatustextOptions,
    connect,
    gcs_statustext_options_from_cfg,
    send_statustext_for_gcs,
)
from valiant.autonomy.gcs_hud import HUD_PREFIX


def _sniff_statustext(connection: str, duration_s: float, out: list[str], errors: list[str]) -> None:
    from pymavlink import mavutil

    master = None
    try:
        master = mavutil.mavlink_connection(connection)
        master.wait_heartbeat(timeout=8)
        deadline = time.time() + duration_s
        while time.time() < deadline:
            msg = master.recv_match(type="STATUSTEXT", blocking=True, timeout=1.0)
            if msg is None:
                continue
            text = msg.text
            if isinstance(text, bytes):
                text = text.decode("utf-8", errors="replace")
            text = text.rstrip("\0").strip()
            if text:
                out.append(text)
    except Exception as exc:
        errors.append(str(exc))
    finally:
        if master is not None:
            try:
                master.close()
            except Exception:
                pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify SITL companion STATUSTEXT reaches Mission Planner Messages",
    )
    parser.add_argument(
        "--connection",
        default=None,
        help="MAVLink URL (default: config mavlink.sitl_connection)",
    )
    parser.add_argument(
        "--listen",
        default="tcp:127.0.0.1:5762",
        help="Optional second port to sniff (Mission Planner SERIAL1). Empty to skip.",
    )
    parser.add_argument("--listen-s", type=float, default=6.0, help="Sniff duration")
    parser.add_argument(
        "--no-mp-sysid",
        action="store_true",
        help="Send only companion sysid 255 (skip autopilot sysid duplicate)",
    )
    args = parser.parse_args()

    cfg = load_config("vion")
    conn = args.connection or cfg.get("mavlink", {}).get(
        "sitl_connection", "tcp:127.0.0.1:5760"
    )
    opts = gcs_statustext_options_from_cfg(cfg, sitl=True)
    if args.no_mp_sysid:
        opts = GcsStatustextOptions(
            severity=opts.severity,
            debug=opts.debug,
            sitl=True,
            mp_use_autopilot_sysid=False,
            sitl_mp_mirror=opts.sitl_mp_mirror,
        )
    opts = GcsStatustextOptions(
        severity=opts.severity,
        debug=True,
        sitl=opts.sitl,
        mp_use_autopilot_sysid=opts.mp_use_autopilot_sysid,
        sitl_mp_mirror=opts.sitl_mp_mirror,
    )

    sniffed: list[str] = []
    sniff_errors: list[str] = []
    sniff_thread: threading.Thread | None = None
    if args.listen:
        sniff_thread = threading.Thread(
            target=_sniff_statustext,
            args=(args.listen, args.listen_s, sniffed, sniff_errors),
            daemon=True,
        )
        sniff_thread.start()
        time.sleep(0.5)

    print(f"Connecting companion -> {conn}")
    try:
        master = connect(conn, wait_heartbeat=True)
    except Exception as exc:
        print(f"FAIL: cannot connect ({exc})")
        print("Start SITL first: .\\tools\\launch_sitl.ps1")
        return 1

    body = "VERIFY statustext"
    print(f"Sending {HUD_PREFIX}{body} (mp_use_autopilot_sysid={opts.mp_use_autopilot_sysid})")
    send_statustext_for_gcs(master, body, prefix=HUD_PREFIX, options=opts)
    master.close()

    if sniff_thread is not None:
        sniff_thread.join(timeout=args.listen_s + 2.0)
        if sniff_errors:
            print(f"\nSniff on {args.listen} failed: {sniff_errors[0]}")
            print("Mission Planner may already be connected to 5762 - disconnect MP and retry,")
            print("or watch MP Messages while this script runs with MP connected.")
        elif sniffed:
            print(f"\nSniff on {args.listen} saw {len(sniffed)} STATUSTEXT line(s):")
            for line in sniffed[-8:]:
                print(f"  {line}")
            hits = [ln for ln in sniffed if "VERIFY" in ln or "T2:" in ln]
            if hits:
                print("\nOK: test STATUSTEXT visible on listen port.")
                return 0
            print("\nWARN: STATUSTEXT on port but not our VERIFY line.")
        else:
            print(f"\nNo STATUSTEXT on {args.listen} within {args.listen_s}s.")
            print("If Mission Planner is on 5762, check MP Messages for T2: VERIFY instead.")

    print("\nManual check (Mission Planner on tcp:127.0.0.1:5762):")
    print("  Messages tab should show: T2: VERIFY statustext")
    print("  MAVLink Inspector (Ctrl+F): filter STATUSTEXT, sysid 1 comp 191")
    print("  Terminal HUD: python tools\\valiant.py gcs monitor")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
