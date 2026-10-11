Competition telemetry client.

The Pi 5 has no battery-backed clock. A wall time before 2026 stays on loopback so a bad clock cannot score latency or a disconnect on every packet. Set the clock before arming.

A live session repeats the last good fix for at most 5 seconds, then stops sending that fix. That cap applies before any live session. Stock SITL keeps the link-lost flags set, so an armed aircraft stays in link-lost until those flags clear. Run `ros2 run telemetry fc_telemetry` with `AEAC_COMP_LIVE` left at 0 to watch the loopback path.
