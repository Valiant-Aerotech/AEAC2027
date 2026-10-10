"""Stream a PX4 position hold. Does not arm and does not change mode.

OffboardControlMode goes out at 10 Hz in every mode. TrajectorySetpoint
goes out only while PX4 is in offboard and a position has been latched.
The latch is taken from a good sample after offboard is enabled, not from
the first sample the node ever sees.
"""

from __future__ import annotations

import sys

try:
    import rclpy
    from px4_msgs.msg import (
        OffboardControlMode,
        TrajectorySetpoint,
        VehicleControlMode,
        VehicleLocalPosition,
    )
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
except ImportError as exc:
    rclpy = None
    OffboardControlMode = None
    TrajectorySetpoint = None
    VehicleControlMode = None
    VehicleLocalPosition = None
    Node = object
    _IMPORT_ERROR: ImportError | None = exc
else:
    _IMPORT_ERROR = None

from offboard.hold_logic import UNUSED, HoldLogic, LocalSample, NAN
from offboard.status import Status

PERIOD_S = 0.1

OFFBOARD_CONTROL_MODE_TOPIC = "/fmu/in/offboard_control_mode"
TRAJECTORY_SETPOINT_TOPIC = "/fmu/in/trajectory_setpoint"
LOCAL_POSITION_TOPIC = "/fmu/out/vehicle_local_position_v1"
CONTROL_MODE_TOPIC = "/fmu/out/vehicle_control_mode"


def _publisher_qos():
    return QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
    )


def _subscription_qos():
    return QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.VOLATILE,
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
    )


class Hold(Node):
    def __init__(self) -> None:
        super().__init__("hold")
        self._logic = HoldLogic()
        self._status = Status(self)
        offboard_topic = self._topic("offboard_control_mode_topic", OFFBOARD_CONTROL_MODE_TOPIC)
        setpoint_topic = self._topic("trajectory_setpoint_topic", TRAJECTORY_SETPOINT_TOPIC)
        local_topic = self._topic("local_position_topic", LOCAL_POSITION_TOPIC)
        control_topic = self._topic("control_mode_topic", CONTROL_MODE_TOPIC)
        self._offboard_pub = self.create_publisher(
            OffboardControlMode,
            offboard_topic,
            _publisher_qos(),
        )
        self._setpoint_pub = self.create_publisher(
            TrajectorySetpoint,
            setpoint_topic,
            _publisher_qos(),
        )
        self.create_subscription(
            VehicleLocalPosition,
            local_topic,
            self._on_position,
            _subscription_qos(),
        )
        self.create_subscription(
            VehicleControlMode,
            control_topic,
            self._on_control_mode,
            _subscription_qos(),
        )
        self.create_timer(PERIOD_S, self._on_timer)

    def _topic(self, name: str, default: str) -> str:
        self.declare_parameter(name, default)
        return str(self.get_parameter(name).value)

    def _on_control_mode(self, msg) -> None:
        try:
            line = self._logic.set_offboard(bool(msg.flag_control_offboard_enabled))
            if line is not None:
                self._status.report(line)
        except Exception as exc:
            self._status.report(f"control mode: {exc}")

    def _on_position(self, msg) -> None:
        try:
            sample = LocalSample(
                x=float(msg.x),
                y=float(msg.y),
                z=float(msg.z),
                heading=float(msg.heading),
                xy_valid=bool(msg.xy_valid),
                z_valid=bool(msg.z_valid),
                heading_good_for_control=bool(msg.heading_good_for_control),
                xy_reset_counter=int(msg.xy_reset_counter),
                z_reset_counter=int(msg.z_reset_counter),
                heading_reset_counter=int(msg.heading_reset_counter),
            )
            line = self._logic.set_sample(sample)
            if line is not None:
                self._status.report(line)
        except Exception as exc:
            self._status.report(f"position: {exc}")

    def _on_timer(self) -> None:
        try:
            self._publish_heartbeat()
            idle = self._logic.idle_line()
            if idle is not None:
                self._status.report(idle)
            setpoint = self._logic.setpoint()
            if setpoint is not None:
                self._publish_setpoint(setpoint)
        except Exception as exc:
            self._status.report(f"publish failed: {exc}")

    def _publish_heartbeat(self) -> None:
        msg = OffboardControlMode()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.position = True
        msg.velocity = False
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        self._offboard_pub.publish(msg)

    def _publish_setpoint(self, setpoint) -> None:
        msg = TrajectorySetpoint()
        msg.timestamp = int(self.get_clock().now().nanoseconds / 1000)
        msg.position = [float(setpoint.x), float(setpoint.y), float(setpoint.z)]
        msg.yaw = float(setpoint.yaw)
        msg.velocity = list(UNUSED)
        msg.acceleration = list(UNUSED)
        msg.jerk = list(UNUSED)
        msg.yawspeed = NAN
        self._setpoint_pub.publish(msg)


def main(args=None) -> None:
    if _IMPORT_ERROR is not None or rclpy is None:
        sys.stderr.write(f"hold: missing ROS dependency: {_IMPORT_ERROR}\n")
        return
    rclpy.init(args=args)
    node = Hold()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        try:
            if rclpy.ok():
                rclpy.shutdown()
        except Exception:
            pass
