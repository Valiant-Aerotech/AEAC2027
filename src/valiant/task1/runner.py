"""Vivi Task 1 field orchestrator."""

from __future__ import annotations

import argparse
from pathlib import Path

from valiant.common.config import load_config
from valiant.task1.detection import TargetEvent, detect, mark_target
from valiant.task1.modes import CameraMode
from valiant.task1.pose import CameraConfig, Pose
from valiant.task1.report import parse
from valiant.task1.survey import setup
from valiant.task1.telemetry import MavlinkTelemetry
from valiant.task1.vector import Vec3


def manual_detector(frame=None) -> str:
    return input("Detected target colour [black/white/red/yellow/blue/green]: ").strip().lower()


def get_current_pose(telemetry: MavlinkTelemetry) -> Pose:
    return telemetry.wait_for_pose(timeout_s=3.0)


def capture_point(name: str, telemetry: MavlinkTelemetry) -> Vec3:
    print(f"\nCapture point: {name}")
    print("Position Vivi at this point, then press Enter.")
    input("Ready to capture? ")
    pose = get_current_pose(telemetry)
    print(
        f"Captured {name}: "
        f"east={pose.position.x:.2f}, north={pose.position.y:.2f}, up={pose.position.z:.2f}, "
        f"yaw={pose.yaw_deg:.1f}, pitch={pose.pitch_deg:.1f}, roll={pose.roll_deg:.1f}"
    )
    return pose.position


def run_setup(telemetry: MavlinkTelemetry):
    print("\n=== SETUP / SURVEY ===")
    print("Capture building corners in this order:")
    print("  A = shared corner")
    print("  B = adjacent corner along one wall")
    print("  C = adjacent corner along perpendicular wall")
    print("A, B, and C must not be collinear.")

    building_height_m = float(input("\nBuilding height [m]: "))
    A = capture_point("Building corner A, shared corner", telemetry)
    B = capture_point("Building corner B, adjacent to A", telemetry)
    C = capture_point("Building corner C, adjacent to A", telemetry)

    door_count_text = input("\nHow many door-frame corners will you capture? [3 or 4, default 3]: ").strip()
    door_count = int(door_count_text or "3")
    if door_count < 3:
        raise ValueError("At least 3 door-frame corners are required.")
    if door_count > 4:
        print("More than 4 was entered; capturing 4 door-frame corners.")
        door_count = 4

    door_points: list[Vec3] = []
    for i in range(door_count):
        door_points.append(capture_point(f"Door-frame corner {i + 1}", telemetry))

    model = setup(
        building_corners=[A, B, C],
        building_height_m=building_height_m,
        door_corners=door_points,
        save_model_path="vivi_building_model_debug.json",
    )

    print("\nSetup complete.")
    print("Detected wall faces:")
    for wall in model.walls:
        door_status = "with door" if wall.door is not None else "no door"
        print(f"  - {wall.name} face, heading {wall.heading_deg:.1f} deg, {door_status}")
    return model


def run_target_search(model, telemetry: MavlinkTelemetry) -> list[TargetEvent]:
    print("\n=== TARGET SEARCH ===")
    target_events: list[TargetEvent] = []
    camera_mode = CameraMode.FRONT

    while True:
        print("\nCommands:")
        print("  f = front camera mode")
        print("  d = down camera mode")
        print("  m = mark target using current MAVLink pose")
        print("  v = view latest MAVLink pose")
        print("  u = undo last target")
        print("  p = parse/write report")
        print("  q = quit without writing")
        print(f"\nCurrent camera mode: {camera_mode.name}")
        print(f"Targets marked: {len(target_events)}")

        cmd = input("\nCommand: ").strip().lower()

        if cmd == "f":
            camera_mode = CameraMode.FRONT
            print("Camera mode set to FRONT.")
        elif cmd == "d":
            camera_mode = CameraMode.DOWN
            print("Camera mode set to DOWN.")
        elif cmd == "v":
            telemetry.print_pose()
        elif cmd == "m":
            print("\nCentre the coloured circle in the camera view, then press Enter.")
            input("Press Enter when target is centred... ")
            colour = detect(None, detector=manual_detector)
            pose = get_current_pose(telemetry)
            event = mark_target(colour=colour, camera_mode=camera_mode, pose=pose)
            target_events.append(event)
            print(
                f"Marked target {len(target_events)}: {colour}, {camera_mode.name}, "
                f"east={pose.position.x:.2f}, north={pose.position.y:.2f}, up={pose.position.z:.2f}"
            )
        elif cmd == "u":
            if target_events:
                removed = target_events.pop()
                print(f"Removed last target: {removed.colour}, {removed.camera_mode.name}")
            else:
                print("No targets to undo.")
        elif cmd == "p":
            return target_events
        elif cmd == "q":
            raise SystemExit("Quit without writing report.")
        else:
            print("Unknown command.")


def run_survey(
    *,
    connection: str | None = None,
    team_name: str | None = None,
    camera_offset_cm: float | None = None,
) -> None:
    cfg = load_config("vivi")
    mavlink_cfg = cfg.get("mavlink", {})
    conn = connection or mavlink_cfg.get("connection", "udpin:127.0.0.1:14550")

    team = team_name or input("Team name for output file: ").strip() or "Valiant_Aerotech"
    if camera_offset_cm is None:
        offset_cm = float(cfg.get("camera", {}).get("offset_cm", 10))
        if team_name is None:
            offset_cm = float(input("Camera vertical offset below GPS/autopilot [cm]: ") or str(offset_cm))
    else:
        offset_cm = camera_offset_cm

    camera = CameraConfig(offset_body_m=Vec3(0.0, 0.0, -offset_cm / 100.0))

    print("Vivi Task 1 Target Localization")
    telemetry = MavlinkTelemetry(conn)
    telemetry.connect(wait_heartbeat=True)
    telemetry.start()

    print("Waiting for first complete pose...")
    first_pose = telemetry.wait_for_pose(timeout_s=10.0)
    print(
        "Telemetry ready: "
        f"east={first_pose.position.x:.2f}, north={first_pose.position.y:.2f}, up={first_pose.position.z:.2f}"
    )

    try:
        model = run_setup(telemetry)
        target_events = run_target_search(model, telemetry)
        output_path = parse(
            events=target_events,
            model=model,
            team_name=team,
            output_dir=None,
            camera=camera,
            include_debug_comments=True,
        )
        print(f"\nReport written: {output_path}")
    finally:
        telemetry.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Vivi Task 1 target localization")
    parser.add_argument("--connection", default=None)
    parser.add_argument("--team", default=None)
    parser.add_argument("--camera-offset-cm", type=float, default=None)
    args = parser.parse_args()
    run_survey(
        connection=args.connection,
        team_name=args.team,
        camera_offset_cm=args.camera_offset_cm,
    )


if __name__ == "__main__":
    main()
