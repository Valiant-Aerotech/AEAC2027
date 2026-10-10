Onboard workspace for the aircraft. ROS 2 Jazzy, on the existing Ubuntu 24.04 WSL distro.

```bash
source /opt/ros/jazzy/setup.bash
colcon build
```

Slots under `src/`:

- `interfaces` — shared messages
- `offboard` — setpoint stream
- `mission` — survey, track log, boundary, 100 m standoff
- `perception` — camera and detection
- `telemetry` — competition telemetry client
- `bringup` — launch files
