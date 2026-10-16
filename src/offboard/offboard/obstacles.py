"""Publish server aircraft as a PX4 obstacle scan, and hold a clear hover target.

Does not arm and does not terminate. Pitch or roll leaves the deadband and
position mode is requested once.

Collision Prevention uses the scan only. It will not move a centered hover.
``CP_DIST`` stays a few metres, ``CP_GO_NO_DATA`` must be 1, and
``MPC_POS_MODE`` must be acceleration-based. This node does not write those.
"""

from __future__ import annotations

import math
import sys
import time

try:
    import rclpy
    from px4_msgs.msg import (
        HomePosition,
        ManualControlSetpoint,
        ObstacleDistance,
        OffboardControlMode,
        TrajectorySetpoint,
        VehicleCommand,
        VehicleControlMode,
        VehicleGlobalPosition,
        VehicleLocalPosition,
        VehicleStatus,
    )
    from rclpy.node import Node
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
    from std_msgs.msg import String
except ImportError as exc:
    rclpy = None
    HomePosition = None
    ManualControlSetpoint = None
    ObstacleDistance = None
    OffboardControlMode = None
    TrajectorySetpoint = None
    VehicleCommand = None
    VehicleControlMode = None
    VehicleGlobalPosition = None
    VehicleLocalPosition = None
    VehicleStatus = None
    String = None
    Node = object
    _IMPORT_ERROR: ImportError | None = exc
else:
    _IMPORT_ERROR = None

from offboard.hold_logic import NAN, UNUSED
from offboard.obstacles_logic import EscapeGate, EscapeTarget, EscapeTargetLatch, LocalSample, TrafficFreshness
from mission.deconflict import TrafficTracks, hover_escape, hover_is_blocked, sector_scan
from telemetry.fc_state import ARMING_STATE_ARMED
from telemetry.traffic import parse_traffic_json

PERIOD_S = 0.1
MODE_PERIOD_S = 1.0
NO_DATA_CM = 65535
MAX_RANGE_CM = 10_000

TRAFFIC_TOPIC = "/aeac/traffic"
OBSTACLE_TOPIC = "/fmu/in/obstacle_distance"
OFFBOARD_TOPIC = "/fmu/in/offboard_control_mode"
SETPOINT_TOPIC = "/fmu/in/trajectory_setpoint"
COMMAND_TOPIC = "/fmu/in/vehicle_command"
GLOBAL_TOPIC = "/fmu/out/vehicle_global_position"
LOCAL_TOPIC = "/fmu/out/vehicle_local_position_v1"
HOME_TOPIC = "/fmu/out/home_position_v2"
STATUS_TOPIC = "/fmu/out/vehicle_status_v4"
STICK_TOPIC = "/fmu/out/manual_control_setpoint_v1"
CONTROL_TOPIC = "/fmu/out/vehicle_control_mode"

OFFBOARD_MODE = 6.0
POSITION_MODE = 3.0


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


def _home_qos():
    return QoSProfile(
        reliability=ReliabilityPolicy.BEST_EFFORT,
        durability=DurabilityPolicy.TRANSIENT_LOCAL,
        history=HistoryPolicy.KEEP_LAST,
        depth=1,
    )


class Obstacles(Node):
    def __init__(self) -> None:
        super().__init__("obstacles")
        self._tracks = TrafficTracks()
        self._freshness = TrafficFreshness()
        self._gate = EscapeGate()
        self._target_latch = EscapeTargetLatch()
        self._warn_at: dict[str, float] = {}
        self._lat: float | None = None
        self._lon: float | None = None
        self._alt: float | None = None
        self._gps_ok = False
        self._home_alt: float | None = None
        self._x = math.nan
        self._y = math.nan
        self._z = math.nan
        self._heading = math.nan
        self._xy_ok = False
        self._z_ok = False
        self._heading_ok = False
        self._xy_reset_counter = 0
        self._z_reset_counter = 0
        self._heading_reset_counter = 0
        self._armed = False
        self._pitch: float | None = None
        self._roll: float | None = None
        self._offboard = False
        self._mode_mono = 0.0
        self._obstacle_pub = self._publisher("obstacle_distance_topic", OBSTACLE_TOPIC, ObstacleDistance)
        self._offboard_pub = self._publisher("offboard_control_mode_topic", OFFBOARD_TOPIC, OffboardControlMode)
        self._setpoint_pub = self._publisher("trajectory_setpoint_topic", SETPOINT_TOPIC, TrajectorySetpoint)
        self._command_pub = self._publisher("vehicle_command_topic", COMMAND_TOPIC, VehicleCommand)
        self._subscribe("traffic_topic", TRAFFIC_TOPIC, String, self._on_traffic, _subscription_qos())
        self._subscribe("vehicle_global_position_topic", GLOBAL_TOPIC, VehicleGlobalPosition, self._on_global, _subscription_qos())
        self._subscribe("local_position_topic", LOCAL_TOPIC, VehicleLocalPosition, self._on_local, _subscription_qos())
        self._subscribe("home_position_topic", HOME_TOPIC, HomePosition, self._on_home, _home_qos())
        self._subscribe("vehicle_status_topic", STATUS_TOPIC, VehicleStatus, self._on_status, _subscription_qos())
        self._subscribe("manual_control_topic", STICK_TOPIC, ManualControlSetpoint, self._on_sticks, _home_qos())
        self._subscribe("control_mode_topic", CONTROL_TOPIC, VehicleControlMode, self._on_control, _subscription_qos())
        self.create_timer(PERIOD_S, self._on_timer)

    def _publisher(self, name: str, default: str, msg_type):
        self.declare_parameter(name, default)
        return self.create_publisher(msg_type, str(self.get_parameter(name).value), _publisher_qos())

    def _subscribe(self, name: str, default: str, msg_type, callback, qos) -> None:
        self.declare_parameter(name, default)
        self.create_subscription(msg_type, str(self.get_parameter(name).value), callback, qos)

    def _warn(self, key: str, line: str) -> None:
        now = time.monotonic()
        last = self._warn_at.get(key)
        if last is not None and now - last < 5.0:
            return
        self._warn_at[key] = now
        self.get_logger().warning(line)

    def _guard(self, label: str, fn) -> None:
        try:
            fn()
        except Exception as exc:
            self._warn(label, f"{label}: {exc}")

    def _on_traffic(self, msg) -> None:
        def take() -> None:
            now = time.monotonic()
            snapshot = parse_traffic_json(str(msg.data))
            self._freshness.observe(self._tracks.observe(snapshot, now), now)

        self._guard("traffic", take)

    def _on_global(self, msg) -> None:
        def take() -> None:
            self._gps_ok = bool(msg.lat_lon_valid) and math.isfinite(float(msg.lat)) and math.isfinite(float(msg.lon))
            if self._gps_ok:
                self._lat = float(msg.lat)
                self._lon = float(msg.lon)
            if bool(msg.alt_valid) and math.isfinite(float(msg.alt)):
                self._alt = float(msg.alt)

        self._guard("global", take)

    def _on_local(self, msg) -> None:
        def take() -> None:
            self._xy_ok = bool(msg.xy_valid)
            self._z_ok = bool(msg.z_valid)
            self._x = float(msg.x)
            self._y = float(msg.y)
            self._z = float(msg.z)
            self._heading = float(msg.heading)
            self._heading_ok = bool(msg.heading_good_for_control)
            self._xy_reset_counter = int(msg.xy_reset_counter)
            self._z_reset_counter = int(msg.z_reset_counter)
            self._heading_reset_counter = int(msg.heading_reset_counter)

        self._guard("local", take)

    def _on_home(self, msg) -> None:
        def take() -> None:
            self._home_alt = float(msg.alt)

        self._guard("home", take)

    def _on_status(self, msg) -> None:
        def take() -> None:
            self._armed = int(msg.arming_state) == ARMING_STATE_ARMED

        self._guard("status", take)

    def _on_sticks(self, msg) -> None:
        def take() -> None:
            if not bool(msg.valid):
                self._pitch = None
                self._roll = None
                return
            pitch = float(msg.pitch)
            roll = float(msg.roll)
            self._pitch = pitch if math.isfinite(pitch) else None
            self._roll = roll if math.isfinite(roll) else None

        self._guard("sticks", take)

    def _on_control(self, msg) -> None:
        def take() -> None:
            self._offboard = bool(msg.flag_control_offboard_enabled)

        self._guard("control", take)

    def _own_alt(self) -> float:
        if self._home_alt is None or self._alt is None:
            return math.nan
        return self._alt - self._home_alt

    def _local_sample(self) -> LocalSample:
        return LocalSample(
            x=self._x,
            y=self._y,
            z=self._z,
            yaw=self._heading,
            xy_valid=self._xy_ok,
            z_valid=self._z_ok,
            heading_good_for_control=self._heading_ok,
            xy_reset_counter=self._xy_reset_counter,
            z_reset_counter=self._z_reset_counter,
            heading_reset_counter=self._heading_reset_counter,
        )

    def _on_timer(self) -> None:
        try:
            now = time.monotonic()
            fresh = self._freshness.fresh(now)
            motions = self._tracks.motions(now)
            bins = (math.inf,) * 72
            north_m = 0.0
            east_m = 0.0
            up_m = 0.0
            if self._gps_ok and self._lat is not None and self._lon is not None:
                alt = self._own_alt()
                bins = sector_scan(self._lat, self._lon, alt, motions)
                if fresh and self._armed:
                    north_m, east_m, up_m = hover_escape(
                        self._lat, self._lon, alt, motions, prefer=self._gate.remembered()
                    )
            self._publish_scan(bins)
            if not fresh:
                self._gate.reset()
                self._target_latch.reset()
                return
            action = self._gate.update(
                armed=self._armed and self._gps_ok,
                pitch=self._pitch,
                roll=self._roll,
                north_m=north_m,
                east_m=east_m,
                up_m=up_m,
            )
            if (
                self._armed
                and self._gps_ok
                and self._lat is not None
                and self._lon is not None
                and hover_is_blocked(self._lat, self._lon, self._own_alt(), motions)
            ):
                self._warn("blocked", "escape blocked")
            if action.mode == "offboard":
                self._warn("offboard", f"escape {north_m:.0f} m north {east_m:.0f} m east {up_m:.0f} m up")
            elif action.mode == "position":
                self._warn("position", "position mode")
            target = self._target_latch.update(action, self._local_sample())
            if target is not None:
                self._publish_heartbeat()
                if self._offboard:
                    self._publish_setpoint(target)
            self._publish_mode(action.mode)
        except Exception as exc:
            self._warn("timer", f"timer: {exc}")

    def _publish_scan(self, bins: tuple[float, ...]) -> None:
        msg = ObstacleDistance()
        msg.timestamp = self._micros()
        msg.frame = int(ObstacleDistance.MAV_FRAME_GLOBAL)
        msg.increment = 5.0
        msg.min_distance = 0
        msg.max_distance = MAX_RANGE_CM
        msg.angle_offset = 0.0
        distances = []
        for metres in bins:
            if not math.isfinite(metres):
                distances.append(NO_DATA_CM)
            elif metres <= 0.0:
                distances.append(0)
            else:
                distances.append(min(MAX_RANGE_CM, int(round(metres * 100.0))))
        msg.distances = distances
        self._obstacle_pub.publish(msg)

    def _publish_heartbeat(self) -> None:
        msg = OffboardControlMode()
        msg.timestamp = self._micros()
        msg.position = True
        msg.velocity = False
        msg.acceleration = False
        msg.attitude = False
        msg.body_rate = False
        self._offboard_pub.publish(msg)

    def _publish_setpoint(self, target: EscapeTarget) -> None:
        msg = TrajectorySetpoint()
        msg.timestamp = self._micros()
        msg.position = [target.x, target.y, target.z]
        msg.yaw = target.yaw
        msg.velocity = list(UNUSED)
        msg.acceleration = list(UNUSED)
        msg.jerk = list(UNUSED)
        msg.yawspeed = NAN
        self._setpoint_pub.publish(msg)

    def _publish_mode(self, mode: str | None) -> None:
        if mode is None:
            return
        now = time.monotonic()
        if mode == "offboard":
            if self._offboard or now - self._mode_mono < MODE_PERIOD_S:
                return
            custom = OFFBOARD_MODE
        else:
            custom = POSITION_MODE
        self._mode_mono = now
        msg = VehicleCommand()
        msg.timestamp = self._micros()
        msg.command = int(VehicleCommand.VEHICLE_CMD_DO_SET_MODE)
        msg.param1 = 1.0
        msg.param2 = custom
        msg.param3 = 0.0
        msg.param4 = 0.0
        msg.param5 = 0.0
        msg.param6 = 0.0
        msg.param7 = 0.0
        msg.target_system = 1
        msg.target_component = 1
        msg.source_system = 1
        msg.source_component = 1
        msg.from_external = True
        msg.confirmation = 0
        self._command_pub.publish(msg)

    def _micros(self) -> int:
        return int(self.get_clock().now().nanoseconds / 1000)


def main(args=None) -> None:
    if _IMPORT_ERROR is not None or rclpy is None:
        sys.stderr.write(f"obstacles: missing ROS dependency: {_IMPORT_ERROR}\n")
        return
    rclpy.init(args=args)
    node = Obstacles()
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
