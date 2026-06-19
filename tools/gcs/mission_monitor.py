#!/usr/bin/env python3
"""GCS read-only mission monitor (UDP telemetry from Pi or SITL host)."""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor onboard mission telemetry")
    parser.add_argument("--port", type=int, default=14560)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.bind(("0.0.0.0", args.port))
    except OSError as exc:
        in_use = getattr(exc, "winerror", None) == 10048 or getattr(exc, "errno", None) in (98, 10048)
        if in_use:
            print(
                f"UDP :{args.port} already in use - another mission monitor is running.",
                file=sys.stderr,
            )
            print("Close the other monitor window or use -NoMonitor on run_sitl_mission.ps1")
            raise SystemExit(0) from exc
        raise
    sock.settimeout(1.0)
    print(f"Listening for telemetry on UDP :{args.port} (Ctrl+C to stop)")
    print(
        f"{'time':>8}  {'state':<12}  {'dist':>12}  {'pos':>14}  {'vel':>14}  "
        f"{'gimbal':>6}  tgt  sitl"
    )
    print("-" * 92)

    while True:
        try:
            data, addr = sock.recvfrom(4096)
        except TimeoutError:
            continue
        try:
            msg = json.loads(data.decode())
        except json.JSONDecodeError:
            continue
        dist = msg.get("dist_m")
        dmin = msg.get("dist_min_m")
        dmax = msg.get("dist_max_m")
        if dmin is not None and dmax is not None:
            dist_s = f"{dmin:.1f}-{dmax:.1f}m"
        elif dist is not None:
            dist_s = f"{dist:.1f}m"
        else:
            dist_s = "?"
        vx = msg.get("vel_x")
        vy = msg.get("vel_y")
        vz = msg.get("vel_z")
        if vx is not None:
            vel_s = f"{vx:.2f},{vy:.2f},{vz:.2f}"
        else:
            vel_s = "?"
        pwm = msg.get("gimbal_pwm")
        pwm_s = str(pwm) if pwm is not None else "?"
        px = msg.get("pos_x")
        py = msg.get("pos_y")
        alt = msg.get("alt_m")
        if px is not None and py is not None:
            pos_s = f"{px:.1f},{py:.1f},{alt or 0:.1f}"
        else:
            pos_s = "?"
        print(
            f"{time.strftime('%H:%M:%S'):>8}  "
            f"{msg.get('state', '?'):<12}  "
            f"{dist_s:>12}  "
            f"{pos_s:>14}  "
            f"{vel_s:>14}  "
            f"{pwm_s:>6}  "
            f"{'Y' if msg.get('target_seen') else 'n'}    "
            f"{'Y' if msg.get('sitl') else 'n'}  "
            f"<- {addr[0]}"
        )


if __name__ == "__main__":
    main()
