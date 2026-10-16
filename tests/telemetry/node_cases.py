"""ROS-independent traffic publication cases for the telemetry node."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "telemetry"))

import telemetry.node as node_module
from telemetry.traffic import TRAFFIC_SNAPSHOT_VERSION, TrafficAircraft, TrafficSnapshot, parse_traffic_json


class FakeMessage:
    def __init__(self) -> None:
        self.data = ""


class FakeClient:
    def __init__(self, snapshot: TrafficSnapshot | None = None) -> None:
        self.snapshot = snapshot

    def traffic_snapshot(self) -> TrafficSnapshot | None:
        return self.snapshot


class FakePublisher:
    def __init__(self) -> None:
        self.messages: list[FakeMessage] = []

    def publish(self, message: FakeMessage) -> None:
        self.messages.append(message)


def snapshot(sequence: int, aircraft: tuple[TrafficAircraft, ...]) -> TrafficSnapshot:
    return TrafficSnapshot(TRAFFIC_SNAPSHOT_VERSION, "session-a", sequence, aircraft)


def test_publish_traffic_once_per_identity() -> None:
    node_module.String = FakeMessage
    client = FakeClient()
    publisher = FakePublisher()
    node = node_module.FcTelemetry.__new__(node_module.FcTelemetry)
    node._client = client
    node._traffic_pub = publisher
    node._published_traffic_identity = None

    node._publish_traffic()
    assert publisher.messages == []

    aircraft = (TrafficAircraft("7", 45.0, -75.0, 42.0, 80.0, 25.0, 180.0),)
    client.snapshot = snapshot(0, aircraft)
    node._publish_traffic()
    node._publish_traffic()
    assert len(publisher.messages) == 1

    client.snapshot = snapshot(1, aircraft)
    node._publish_traffic()
    assert len(publisher.messages) == 2
    assert parse_traffic_json(publisher.messages[-1].data) == client.snapshot

    client.snapshot = snapshot(2, ())
    node._publish_traffic()
    assert len(publisher.messages) == 3
    assert parse_traffic_json(publisher.messages[-1].data).aircraft == ()


if __name__ == "__main__":
    test_publish_traffic_once_per_identity()
    print("[>] telemetry node cases ok")
