"""Plain asserts for the versioned traffic snapshot contract."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "telemetry"))

from telemetry.traffic import (
    TRAFFIC_SNAPSHOT_VERSION,
    TrafficAircraft,
    TrafficSnapshot,
    TrafficSnapshotError,
    parse_traffic,
    parse_traffic_json,
    traffic_json,
)


def server_row(aircraft_id: str = "7") -> dict[str, object]:
    return {
        "aircraftIndex": aircraft_id,
        "horizontalKeepAway": 80.0,
        "verticalKeepAway": 25.0,
        "position": {
            "lat": 45.4215,
            "lon": -75.6972,
            "altitude": 42.0,
            "direction": 180.0,
        },
    }


def assert_rejected(call) -> None:
    try:
        call()
    except TrafficSnapshotError:
        return
    raise AssertionError("expected TrafficSnapshotError")


def test_heading_preserving_round_trip() -> None:
    aircraft = parse_traffic({"event": "traffic", "payload": {"traffic": [server_row()]}})
    snapshot = TrafficSnapshot(TRAFFIC_SNAPSHOT_VERSION, "session-a", 4, aircraft)
    assert parse_traffic_json(traffic_json(snapshot)) == snapshot
    assert snapshot.aircraft[0].heading_deg == 180.0


def test_empty_snapshots_are_valid() -> None:
    aircraft = parse_traffic({"traffic": []})
    snapshot = TrafficSnapshot(TRAFFIC_SNAPSHOT_VERSION, "session-a", 5, aircraft)
    assert aircraft == ()
    assert parse_traffic_json(traffic_json(snapshot)) == snapshot


def test_server_rows_reject_duplicates_atomically() -> None:
    valid = server_row("7")
    duplicate = server_row("7")
    duplicate["position"] = {"lat": 1.0, "lon": 2.0, "altitude": 3.0}
    assert_rejected(lambda: parse_traffic({"traffic": [valid, duplicate]}))


def test_server_rows_reject_malformed_and_non_finite_values() -> None:
    assert_rejected(lambda: parse_traffic({"traffic": [server_row(), "bad-row"]}))
    for field, value in (
        ("lat", math.nan),
        ("lon", math.inf),
        ("altitude", -math.inf),
        ("direction", math.nan),
    ):
        row = server_row()
        row["position"][field] = value
        assert_rejected(lambda row=row: parse_traffic({"traffic": [row]}))


def test_server_rows_require_positive_keepout_dimensions() -> None:
    for field, value in (
        ("horizontalKeepAway", 0.0),
        ("horizontalKeepAway", math.inf),
        ("verticalKeepAway", -1.0),
        ("verticalKeepAway", math.nan),
    ):
        row = server_row()
        row[field] = value
        assert_rejected(lambda row=row: parse_traffic({"traffic": [row]}))


def test_ros_snapshot_rejects_bad_metadata_and_rows() -> None:
    snapshot = TrafficSnapshot(
        TRAFFIC_SNAPSHOT_VERSION,
        "session-a",
        6,
        (TrafficAircraft("7", 45.0, -75.0, 42.0, 80.0, 25.0, 180.0),),
    )
    payload = json.loads(traffic_json(snapshot))
    for field, value in (
        ("version", 2),
        ("session_id", ""),
        ("sequence", -1),
        ("sequence", True),
    ):
        invalid = dict(payload)
        invalid[field] = value
        assert_rejected(lambda invalid=invalid: parse_traffic_json(json.dumps(invalid)))

    duplicate = dict(payload)
    duplicate["aircraft"] = payload["aircraft"] * 2
    assert_rejected(lambda: parse_traffic_json(json.dumps(duplicate)))

    invalid_dimension = json.loads(traffic_json(snapshot))
    invalid_dimension["aircraft"][0]["keepout_radius_m"] = 0.0
    assert_rejected(lambda: parse_traffic_json(json.dumps(invalid_dimension)))


if __name__ == "__main__":
    test_heading_preserving_round_trip()
    test_empty_snapshots_are_valid()
    test_server_rows_reject_duplicates_atomically()
    test_server_rows_reject_malformed_and_non_finite_values()
    test_server_rows_require_positive_keepout_dimensions()
    test_ros_snapshot_rejects_bad_metadata_and_rows()
    print("[>] traffic cases ok")