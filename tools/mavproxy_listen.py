#!/usr/bin/env python3
"""Debug MAVLink stream - print STATUSTEXT messages."""

from __future__ import annotations

import argparse

from pymavlink import mavutil


def main() -> None:
    parser = argparse.ArgumentParser(description="Listen for MAVLink STATUSTEXT messages")
    parser.add_argument("--connection", default="udpin:127.0.0.1:14550")
    args = parser.parse_args()

    print(f"Listening on {args.connection} (Ctrl+C to stop)")
    master = mavutil.mavlink_connection(args.connection)
    master.wait_heartbeat()
    print(f"Heartbeat from system {master.target_system}")

    while True:
        msg = master.recv_match(type="STATUSTEXT", blocking=True)
        if msg:
            print(f"STATUSTEXT: {msg.text}")


if __name__ == "__main__":
    main()
