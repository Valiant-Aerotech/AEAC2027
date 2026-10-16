# Offboard

`obstacles` is the sole owner of PX4 trajectory setpoints. It publishes
`/fmu/in/obstacle_distance` from retained `/aeac/traffic` tracks and can move
an armed aircraft away from traffic while pitch and roll remain centered.
The node does not arm the aircraft.

Traffic must contain a newly accepted snapshot less than two seconds old.
Duplicate snapshots do not renew freshness. When an escape is required, the
node latches one absolute local-position target, starts the Offboard heartbeat,
and requests Offboard once per second until PX4 confirms it. A trajectory
setpoint is published only after that confirmation.

Stale traffic, invalid local position or heading, or an XY, Z, or heading
estimator reset clears the target. Moving pitch or roll outside the deadband,
or reaching a legal hover, requests Position mode once and does not command a
return to the previous point.

Topic parameters, if the defaults do not match `ros2 topic list | grep fmu`:

- `traffic_topic` default `/aeac/traffic`
- `obstacle_distance_topic` default `/fmu/in/obstacle_distance`
- `offboard_control_mode_topic` default `/fmu/in/offboard_control_mode`
- `trajectory_setpoint_topic` default `/fmu/in/trajectory_setpoint`
- `vehicle_command_topic` default `/fmu/in/vehicle_command`
- `vehicle_global_position_topic` default `/fmu/out/vehicle_global_position`
- `local_position_topic` default `/fmu/out/vehicle_local_position_v1`
- `home_position_topic` default `/fmu/out/home_position_v2`
- `vehicle_status_topic` default `/fmu/out/vehicle_status_v4`
- `manual_control_topic` default `/fmu/out/manual_control_setpoint_v1`
- `control_mode_topic` default `/fmu/out/vehicle_control_mode`

Before trusting silence from the node, use `ros2 topic info -v` to verify topic
names and QoS. If Offboard is refused, check that
`/fmu/in/offboard_control_mode` is publishing at about 10 Hz during an active
escape.

Leave `CP_DIST` at a few metres, set `CP_GO_NO_DATA` to 1, and set
`MPC_POS_MODE` to acceleration-based. The node does not write these parameters.
