"""Publish competition telemetry from PX4. Does not arm or command.

The 10 Hz timer only stores the latest sample and calls ``tick``. The
client keeps the send gap. Streaming topics are best-effort and volatile.
Home is best-effort and transient-local, because PX4 publishes it when
home is set and then can go quiet.
"""

from __future__ import annotations

import math
import sys
import time

try:
    import rclpy
    from px4_msgs.msg import BatteryStatus, FailsafeFlags, HomePosition, VehicleGlobalPosition, VehicleGnss, VehicleStatus
    from rclpy.node import Node
    from std_msgs.msg import String
    from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
except ImportError as exc:
    rclpy = None
    BatteryStatus = None
    FailsafeFlags = None
    HomePosition = None
    VehicleGlobalPosition = None
    VehicleGnss = None
    VehicleStatus = None
    String = None
    Node = object
    _IMPORT_ERROR: ImportError | None = exc
else:
    _IMPORT_ERROR = None

from telemetry.client import make_client
from telemetry.traffic import traffic_json
from telemetry.fc_state import (
    AGL_WARN_M,
    ARMING_STATE_ARMED,
    BATTERY_HELD_AFTER_S,
    ground_bias_m,
    packet_from_fc,
)

PERIOD_S = 0.1
WARN_PERIOD_S = 5.0

STATUS_TOPIC = "/fmu/out/vehicle_status_v4"
BATTERY_TOPIC = "/fmu/out/battery_status_v1"
HOME_TOPIC = "/fmu/out/home_position_v2"
FAILSAFE_TOPIC = "/fmu/out/failsafe_flags"
GNSS_TOPIC = "/fmu/out/vehicle_gnss"
GLOBAL_TOPIC = "/fmu/out/vehicle_global_position"
TRAFFIC_TOPIC = "/aeac/traffic"


def _stream_qos():
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


class FcTelemetry(Node):
    def __init__(self) -> None:
        super().__init__("fc_telemetry")
        self._client = make_client()
        self._warn_at: dict[str, float] = {}
        self._have_status = False
        self._arming = 0
        self._nav = 0
        self._failsafe = False
        self._gcs_lost = False
        self._rc_lost = False
        self._lat: float | None = None
        self._lon: float | None = None
        self._alt: float | None = None
        self._eph: float | None = None
        self._pos_mono: float | None = None
        self._fix_usable = False
        self._fix_type: int | None = None
        self._home_alt: float | None = None
        self._home_logged = False
        self._frame_bias = 0.0
        self._battery_pct: float | None = None
        self._battery_mono: float | None = None
        self._published_traffic_identity: tuple[str, int] | None = None
        self.declare_parameter("traffic_topic", TRAFFIC_TOPIC)
        traffic_topic = str(self.get_parameter("traffic_topic").value)
        self._traffic_pub = self.create_publisher(String, traffic_topic, _stream_qos())
        self._subscribe("vehicle_status_topic", STATUS_TOPIC, VehicleStatus, self._on_status, _stream_qos())
        self._subscribe("battery_status_topic", BATTERY_TOPIC, BatteryStatus, self._on_battery, _stream_qos())
        self._subscribe("home_position_topic", HOME_TOPIC, HomePosition, self._on_home, _home_qos())
        self._subscribe("failsafe_flags_topic", FAILSAFE_TOPIC, FailsafeFlags, self._on_failsafe, _stream_qos())
        self._subscribe("vehicle_gnss_topic", GNSS_TOPIC, VehicleGnss, self._on_gnss, _stream_qos())
        self._subscribe("vehicle_global_position_topic", GLOBAL_TOPIC, VehicleGlobalPosition, self._on_global, _stream_qos())
        self.create_timer(PERIOD_S, self._on_timer)

    def _subscribe(self, name: str, default: str, msg_type, callback, qos) -> None:
        self.declare_parameter(name, default)
        topic = str(self.get_parameter(name).value)
        self.create_subscription(msg_type, topic, callback, qos)

    def _warn(self, key: str, line: str) -> None:
        now = time.monotonic()
        last = self._warn_at.get(key)
        if last is not None and now - last < WARN_PERIOD_S:
            return
        self._warn_at[key] = now
        self.get_logger().warning(line)

    def _guard(self, label: str, fn) -> None:
        try:
            fn()
        except Exception as exc:
            self._warn(label, f"{label}: {exc}")

    def _on_status(self, msg) -> None:
        def take() -> None:
            self._arming = int(msg.arming_state)
            self._nav = int(msg.nav_state)
            self._failsafe = bool(msg.failsafe)
            self._gcs_lost = bool(msg.gcs_connection_lost)
            self._have_status = True

        self._guard("status", take)

    def _on_battery(self, msg) -> None:
        def take() -> None:
            remaining = float(msg.remaining)
            if not math.isfinite(remaining):
                return
            self._battery_pct = remaining * 100.0
            self._battery_mono = time.monotonic()

        self._guard("battery", take)

    def _on_home(self, msg) -> None:
        def take() -> None:
            self._home_alt = float(msg.alt)
            self._capture_frame()

        self._guard("home", take)

    def _on_failsafe(self, msg) -> None:
        def take() -> None:
            self._rc_lost = bool(msg.manual_control_signal_lost)

        self._guard("failsafe", take)

    def _on_gnss(self, msg) -> None:
        def take() -> None:
            self._fix_usable = bool(msg.usable)
            self._fix_type = int(msg.receiver.fix_type)

        self._guard("gnss", take)

    def _on_global(self, msg) -> None:
        def take() -> None:
            if bool(msg.lat_lon_valid):
                self._lat = float(msg.lat)
                self._lon = float(msg.lon)
                self._eph = float(msg.eph)
                self._pos_mono = time.monotonic()
            if bool(msg.alt_valid):
                self._alt = float(msg.alt)
            self._capture_frame()

        self._guard("global", take)

    def _capture_frame(self) -> None:
        if self._home_logged or self._home_alt is None or self._alt is None:
            return
        self._home_logged = True
        on_ground = self._arming != ARMING_STATE_ARMED
        self._frame_bias = ground_bias_m(self._alt, self._home_alt, on_ground=on_ground)
        self.get_logger().warning(f"home {self._home_alt:.1f} m global {self._alt:.1f} m")

    def _publish_traffic(self) -> None:
        snapshot = self._client.traffic_snapshot()
        if snapshot is None:
            return
        identity = (snapshot.session_id, snapshot.sequence)
        if identity == self._published_traffic_identity:
            return
        message = String()
        message.data = traffic_json(snapshot)
        self._traffic_pub.publish(message)
        self._published_traffic_identity = identity

    def _on_timer(self) -> None:
        try:
            if not self._have_status:
                return
            now = time.monotonic()
            if self._home_alt is None:
                self._warn("home", "no home")
            if self._battery_pct is not None and self._battery_mono is not None:
                battery_age = now - self._battery_mono
                if battery_age > BATTERY_HELD_AFTER_S:
                    self._warn("battery", f"battery held {battery_age:.0f} s")
            age = None if self._pos_mono is None else now - self._pos_mono
            packet = packet_from_fc(
                uav_id=self._client.uav_id,
                arming_state=self._arming,
                nav_state=self._nav,
                failsafe=self._failsafe,
                gcs_connection_lost=self._gcs_lost,
                manual_control_signal_lost=self._rc_lost,
                lat=self._lat,
                lon=self._lon,
                alt_amsl_m=self._alt,
                eph_m=self._eph,
                position_age_s=age,
                fix_usable=self._fix_usable,
                fix_type=self._fix_type,
                home_alt_m=self._home_alt,
                frame_bias_m=self._frame_bias,
                battery_pct=self._battery_pct,
            )
            if packet.alt_agl_m <= AGL_WARN_M:
                self._warn("agl", f"agl {packet.alt_agl_m:.0f} m")
            self._client.tick(packet)
            self._publish_traffic()
        except Exception as exc:
            self._warn("tick", f"tick failed: {exc}")


def main(args=None) -> None:
    if _IMPORT_ERROR is not None or rclpy is None:
        sys.stderr.write(f"fc_telemetry: missing ROS dependency: {_IMPORT_ERROR}\n")
        return
    rclpy.init(args=args)
    node = FcTelemetry()
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
