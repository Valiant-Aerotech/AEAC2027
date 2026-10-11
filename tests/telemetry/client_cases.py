"""Plain asserts for loopback and the live send clock. No ROS."""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "telemetry"))

from telemetry.client import (
    HOLD_FIX_S,
    SEND_FLOOR_S,
    SEND_PERIOD_S,
    CompetitionClient,
    LiveSession,
    make_client,
    send_due,
)
from telemetry.packet import TelemetryPacket
from telemetry.secrets import CompetitionSecrets
from telemetry.traffic import parse_traffic

WALL = 1_800_000_000.0


class FakeSocket:
    def __init__(self):
        self.sent: list[str] = []
        self._inbox = [json.dumps({"event": "telemetry_ack", "mode": "armed-automatic"})]
        self.timeouts: list[float] = []

    def settimeout(self, value: float) -> None:
        self.timeouts.append(value)

    def send(self, data: str) -> None:
        self.sent.append(data)

    def recv(self) -> str:
        if not self._inbox:
            raise TimeoutError("no message")
        return self._inbox.pop(0)

    def close(self) -> None:
        pass


def packet(mode: str = "armed-automatic", **changes) -> TelemetryPacket:
    base = TelemetryPacket(
        uav_id="valiant-1",
        timestamp=WALL,
        lat=50.09807,
        lon=-110.73566,
        alt_agl_m=45.0,
        accuracy_m=1.2,
        battery_pct=90.0,
        flight_mode=mode,
        link_quality=1,
    )
    return replace(base, **changes) if changes else base


def test_send_floor_and_period() -> None:
    assert SEND_FLOOR_S == 0.5
    assert SEND_PERIOD_S == 0.9
    assert send_due(None, 0.0, 0.49) is False
    assert send_due(None, 0.0, 0.5) is True
    assert send_due(0.0, 0.0, 0.5) is False
    assert send_due(0.0, 0.0, 0.9) is True


def test_loopback_sends_inside_tick() -> None:
    client = CompetitionClient(uav_id="valiant-1")
    assert client.tick(packet(), now=10.0, wall=WALL) is True
    assert client.status.packets_sent == 1
    assert client.telemetry_ready() is True
    assert len(client.transport.sent) == 1
    assert client.tick(packet(), now=10.2, wall=WALL) is False
    assert client.status.packets_sent == 1
    assert client.tick(packet("idle"), now=20.0, wall=WALL) is False
    assert len(client.transport.sent) == 1


def test_live_tick_does_not_open_a_socket() -> None:
    opened: list[int] = []

    def connect():
        opened.append(threading.get_ident())
        raise AssertionError("tick opened a socket")

    client = CompetitionClient(uav_id="valiant-1", _clock=lambda: WALL)
    client._live = LiveSession(client, connect)
    assert client.tick(packet(), now=10.0, wall=WALL) is False
    assert opened == []
    assert client.status.packets_sent == 0
    assert client.telemetry_ready() is False


def test_write_then_ack() -> None:
    sock = FakeSocket()
    client = CompetitionClient(uav_id="valiant-1", _clock=lambda: WALL)
    session = LiveSession(client, lambda: sock)
    client._live = session
    client.tick(packet(timestamp=1.0))
    session.pump_once()
    assert client.status.packets_sent == 1
    assert client.telemetry_ready() is False
    body = json.loads(sock.sent[0])
    assert body["action"] == "telemetry"
    assert body["data"]["uavId"] == "valiant-1"
    assert body["data"]["unixTime"] == WALL
    assert body["data"]["mode"] == "armed-automatic"
    session.pump_once()
    assert client.telemetry_ready() is True


def test_live_hold_stops_after_five_seconds() -> None:
    client = CompetitionClient(uav_id="valiant-1")
    good = packet(timestamp=1_000.0)
    bad = packet(timestamp=1_006.0, accuracy_m=0.0)
    with client._lock:
        client._latest = good
        held = client._prepare_live(10.0, 1_004.0)
        assert held is not None
        assert held.accuracy_m == 1.2
        client._latest = bad
        still = client._prepare_live(11.0, 1_004.9)
        assert still is not None
        assert still.lat == good.lat
        dropped = client._prepare_live(12.0, 1_000.0 + HOLD_FIX_S)
    assert dropped is None
    assert client.status.last_penalty is not None
    assert client.status.last_penalty.kind.value == "invalid_gps"


def test_bad_clock_stays_on_loopback() -> None:
    client = make_client(
        secrets=CompetitionSecrets(
            token="secret-token",
            url="ws://127.0.0.1:9/telemetry",
            uav_id="valiant-1",
            live=True,
        ),
        clock=lambda: 1_000_000.0,
    )
    assert client._live is None
    assert client.transport.__class__.__name__ == "LoopbackTransport"


def test_traffic_payload_shape() -> None:
    traffic = parse_traffic(
        {
            "event": "traffic",
            "payload": {
                "traffic": [
                    {
                        "aircraftIndex": 0,
                        "position": {"lat": 50.1, "lon": -110.7, "altitude": 40, "direction": 180},
                    }
                ]
            },
        }
    )
    assert traffic[0].uav_id == "0"
    assert traffic[0].alt_agl_m == 40
    assert traffic[0].heading_deg == 180


if __name__ == "__main__":
    test_send_floor_and_period()
    test_loopback_sends_inside_tick()
    test_live_tick_does_not_open_a_socket()
    test_write_then_ack()
    test_live_hold_stops_after_five_seconds()
    test_bad_clock_stays_on_loopback()
    test_traffic_payload_shape()
    print("client cases ok")
