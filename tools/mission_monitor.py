#!/usr/bin/env python3
"""GCS read-only mission monitor (UDP telemetry from Pi)."""

from __future__ import annotations

import argparse
import json
import socket
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor onboard mission telemetry")
    parser.add_argument("--port", type=int, default=14560)
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", args.port))
    sock.settimeout(1.0)
    print(f"Listening for Pi telemetry on UDP :{args.port} (Ctrl+C to stop)")
    print(f"{'time':>8}  {'state':<12}  {'dist':>12}  {'src':<12}  tgt  depth  hand")
    print("-" * 70)

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
        print(
            f"{time.strftime('%H:%M:%S'):>8}  "
            f"{msg.get('state', '?'):<12}  "
            f"{dist_s:>12}  "
            f"{msg.get('distance_source', ''):<12}  "
            f"{'Y' if msg.get('target_seen') else 'n'}    "
            f"{'Y' if msg.get('depth_ok') else 'n'}    "
            f"{'Y' if msg.get('hand_test') else 'n'}  "
            f"<- {addr[0]}"
        )


if __name__ == "__main__":
    main()
