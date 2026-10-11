Position hold for PX4. The heartbeat runs at 10 Hz in every mode. A position setpoint is published only while PX4 reports offboard and a local position has been latched. The node does not arm and does not change mode.

Faults are logged and published on `/hold/status_text` (50 characters, same line at most every 5 seconds). QGroundControl will not show that text until a firmware bridge forwards it.

Topic parameters, if the defaults do not match `ros2 topic list | grep fmu`:

- `offboard_control_mode_topic` default `/fmu/in/offboard_control_mode`
- `trajectory_setpoint_topic` default `/fmu/in/trajectory_setpoint`
- `local_position_topic` default `/fmu/out/vehicle_local_position_v1`
- `control_mode_topic` default `/fmu/out/vehicle_control_mode`

Before trusting silence from the node, run `ros2 topic info -v` on the local-position topic and the control-mode topic. A QoS mismatch on either one looks the same as a wrong name.

If `commander mode offboard` is refused, check `ros2 topic hz /fmu/in/offboard_control_mode` and the publisher QoS before publishing setpoints any earlier. The heartbeat should be about 10 Hz the whole time.
