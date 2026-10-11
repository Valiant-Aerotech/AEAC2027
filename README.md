we're using ROS 2 Jazzy, on the Ubuntu 24.04
after installing ros, use these cmds
```bash
source /opt/ros/jazzy/setup.bash
colcon build
```

folders under `src/`:

- `interfaces` — shared messages
- `offboard` — setpoint stream
- `mission` — survey, track log, boundary, 100 m standoff
- `perception` — camera and detection
- `telemetry` — competition telemetry client
- `bringup` — launch files
