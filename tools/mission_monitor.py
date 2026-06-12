#!/usr/bin/env python3
"""GCS mission monitor: MAVLink link quality meter + mission telemetry."""

from __future__ import annotations

import argparse
import sys
import time

from pymavlink import mavutil

from valiant.common.config import load_config


def _link_state(age_s: float, timeout_s: float, rtt_ms: float | None, degraded_rtt_ms: float) -> str:
    if age_s > timeout_s:
        return "LOST"
    if rtt_ms is not None and rtt_ms > degraded_rtt_ms:
        return "DEGRADED"
    return "GOOD"


def main() -> int:
    parser = argparse.ArgumentParser(description="GCS mission monitor")
    parser.add_argument("--connection", default=None)
    args = parser.parse_args()

    cfg = load_config("vion")
    gcs_cfg = cfg.get("gcs_monitor", {})
    conn = args.connection or gcs_cfg.get("connection", "udpin:0.0.0.0:14550")
    timeout_s = gcs_cfg.get("heartbeat_timeout_s", 2.0)
    degraded_rtt_ms = gcs_cfg.get("degraded_rtt_ms", 200)

    print(f"Listening on {conn} (Ctrl+C to quit)")
    master = mavutil.mavlink_connection(conn)
    last_heartbeat = 0.0
    last_rtt_ms: float | None = None
    last_dist_m: float | None = None
    last_statustext = ""

    while True:
        msg = master.recv_match(blocking=True, timeout=1.0)
        now = time.time()
        if msg is None:
            age = now - last_heartbeat if last_heartbeat else 999.0
            state = _link_state(age, timeout_s, last_rtt_ms, degraded_rtt_ms)
            print(f"\r[{state}] waiting for telemetry...", end="", flush=True)
            continue

        mtype = msg.get_type()
        if mtype == "HEARTBEAT" and msg.get_srcComponent() == 191:
            last_heartbeat = now
        elif mtype == "STATUSTEXT":
            last_statustext = msg.text
        elif mtype == "NAMED_VALUE_FLOAT":
            name = msg.name.rstrip("\0")
            if name == "dist_m":
                last_dist_m = msg.value
        elif mtype == "PING":
            last_rtt_ms = (now - (msg.time_usec / 1e6)) * 1000.0

        age = now - last_heartbeat if last_heartbeat else 999.0
        state = _link_state(age, timeout_s, last_rtt_ms, degraded_rtt_ms)
        rtt_txt = f"{last_rtt_ms:.0f}ms" if last_rtt_ms is not None else "n/a"
        dist_txt = f"{last_dist_m:.2f}m" if last_dist_m is not None else "n/a"
        print(
            f"\r[{state}] rtt={rtt_txt} dist={dist_txt} msg={last_statustext[:40]:<40}",
            end="",
            flush=True,
        )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        raise SystemExit(0)
