"""Task 2 state machine - CV -> Metric Recon -> Auto-Nav -> Spray -> Upload."""

from __future__ import annotations

import argparse
import os
import time

import cv2
from pymavlink import mavutil

from valiant.autonomy.auto_nav.mavlink_driver import MavlinkDriver
from valiant.autonomy.auto_nav.planner import MotionIntent, MotionPlanner
from valiant.autonomy.cv.detector import TargetDetector
from valiant.autonomy.cv.exceptions import BadFrameError, CVError, LowConfidenceError
from valiant.autonomy.cv.ui import draw_overlay
from valiant.autonomy.metric_recon.reconstructor import MetricReconstructor
from valiant.autonomy.packets import CVPacket, MetricPacket
from valiant.autonomy.conops import (
    has_shot_confirmation,
    max_targets_for_window,
    post_spray_settle_s,
    require_shot_confirmation,
    shot_confirm_timeout_s,
    task2_photo_filename,
    validate_conops_config,
)
from valiant.autonomy.safety.monitor import SafetyAbort, SafetyMonitor
from valiant.autonomy.spray.actuation import WaterTrigger
from valiant.autonomy.spray.aim import is_aimed
from valiant.autonomy.gimbal.servo_gimbal import GimbalController
from valiant.autonomy.upload.drive import DriveUploader
from valiant.common.camera_factory import (
    camera_depth_mm,
    camera_depth_ok,
    camera_synthetic_cv,
    create_camera,
)
from valiant.common.config import load_config
from valiant.common.mavlink import connect, request_sys_status_stream, send_rtl, send_statustext

STATE_SEARCHING = "SEARCHING"
STATE_APPROACHING = "APPROACHING"
STATE_AIMING = "AIMING"
STATE_FIRING = "FIRING"
STATE_VERIFYING = "VERIFYING"
STATE_CAPTURING = "CAPTURING"
STATE_UPLOADING = "UPLOADING"
STATE_COMPLETE = "COMPLETE"
STATE_ABORTED = "ABORTED"


class AutoExtinguisher:
    """Onboard or GCS autonomous fire extinguishing orchestrator."""

    def __init__(
        self,
        cfg: dict,
        *,
        connection_string: str,
        baudrate: int,
        sim_mode: bool = False,
        sitl_mode: bool = False,
        headless: bool = False,
        phone_ip: str | None = None,
        max_targets: int | None = None,
        hand_test: bool = False,
        gcs_ip: str | None = None,
        video_path: str | None = None,
    ):
        self.cfg = cfg
        self.sim = sim_mode
        self.sitl = sitl_mode
        self.headless = headless
        self.hand_test = hand_test
        nav = cfg.get("auto_nav", {})
        cv_cfg = cfg.get("cv", {})
        team = cfg.get("team", {})

        self.max_frames_without_target = cv_cfg.get("max_frames_without_target", 30)
        self.approach_timeout_s = nav.get("approach_timeout_s", 30)
        self.lock_duration_s = nav.get("lock_duration_s", 1.5)
        self.lock_timeout_s = nav.get("lock_timeout_s", 10)
        self.approach_speed = nav.get("approach_speed", 0.3)
        self.photo_save_dir = team.get("photo_save_dir", "task2_photos")
        self.shoot_duration_s = cfg.get("spray", {}).get("duration_s", 2.0)
        self.cv_method = cv_cfg.get("method", "hsv")
        self.camera_down = cfg.get("metric_recon", {}).get("camera_down", True)
        self.require_shot = require_shot_confirmation(cfg)
        self.shot_confirm_timeout_s = shot_confirm_timeout_s(cfg)
        self.post_spray_settle_s = post_spray_settle_s(cfg)
        self.max_targets = max_targets if max_targets is not None else max_targets_for_window(cfg)
        self.target_number = 1
        self.targets_completed = 0

        for warning in validate_conops_config(cfg):
            print(f"[CONOPS] Warning: {warning}")

        print(f"[INIT] Connecting MAVLink on {connection_string} (sim={sim_mode}, sitl={sitl_mode})...")
        if sim_mode and not sitl_mode:
            self.master = mavutil.mavlink_connection(connection_string, baud=baudrate)
        else:
            self.master = connect(connection_string, baudrate, wait_heartbeat=True)
            print("[INIT] Heartbeat received")

        if not sim_mode or sitl_mode:
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
                10,
                1,
            )
            request_sys_status_stream(self.master, rate_hz=2)

        self.nav = MavlinkDriver(self.master, cfg)
        self.gimbal = GimbalController(self.master, cfg)
        self.safety = SafetyMonitor(self.master, cfg, sim=sim_mode and not sitl_mode)
        self.planner = MotionPlanner(cfg)
        self.metric_recon = MetricReconstructor(self.master, cfg, sim=sim_mode and not sitl_mode)
        self.trigger = WaterTrigger(self.master, cfg)
        self.uploader = DriveUploader(cfg)
        self.detector = TargetDetector(cfg)

        self.camera = create_camera(cfg, phone_ip=phone_ip, video_path=video_path)
        self._telemetry = None
        if gcs_ip:
            from valiant.autonomy.telemetry_bridge import TelemetryBridge

            port = int(cfg.get("gcs_monitor", {}).get("port", 14560))
            self._telemetry = TelemetryBridge(gcs_ip, port=port)
            print(f"[Telemetry] GCS monitor -> {gcs_ip}:{port}")

        self.state = STATE_SEARCHING
        self.frames_without_target = 0
        self.lock_start_time: float | None = None
        self.state_start_time = time.time()
        self.last_hud_alert_time = 0.0
        self.confirm_frame = None
        self.upload_file_path: str | None = None
        self._last_cv: CVPacket | None = None
        self._last_metric: MetricPacket | None = None
        self._stop_loop = False

    def request_stop(self) -> None:
        self._stop_loop = True

    def send_hud_message(self, message: str) -> None:
        send_statustext(self.master, message, prefix="T2: ")

    def set_state(self, new_state: str) -> None:
        if self.state != new_state:
            msg = f"STATE: {self.state} -> {new_state}"
            print(f">>> {msg}")
            self.send_hud_message(msg)
            self.state = new_state
            self.state_start_time = time.time()
            if new_state == STATE_SEARCHING:
                self.lock_start_time = None
                self.planner.reset_approach()
            if new_state == STATE_APPROACHING:
                self.planner.reset_approach()

    def _run_cv(self, frame) -> CVPacket | None:
        synthetic = camera_synthetic_cv(self.camera)
        if synthetic is not None:
            self._last_cv = synthetic
            return synthetic
        try:
            packet = self.detector.detect(frame)
            self._last_cv = packet
            return packet
        except BadFrameError as exc:
            print(f"[CV] Bad frame: {exc}")
            return None
        except LowConfidenceError as exc:
            print(f"[CV] Low confidence: {exc}")
            return self._last_cv
        except CVError as exc:
            print(f"[CV] Error: {exc}")
            return None

    def _run_metric(self, cv_packet: CVPacket | None, frame_w: int, frame_h: int) -> MetricPacket | None:
        if cv_packet is None or not cv_packet.has_dry_target:
            return None
        metric = self.metric_recon.reconstruct(
            cv_packet,
            frame_w,
            frame_h,
            depth_mm=camera_depth_mm(self.camera),
        )
        self._last_metric = metric
        return metric

    def _publish_telemetry(self, cv_packet: CVPacket | None, metric: MetricPacket | None) -> None:
        if self._telemetry is None:
            return
        vel = self.nav.servo.last_vel_body if self._allow_motion() else (0.0, 0.0, 0.0)
        gimbal_pwm = self.gimbal.current_pwm if self.gimbal.enabled else None
        self._telemetry.send(
            state=self.state,
            distance_m=metric.distance_m if metric else None,
            distance_min_m=metric.distance_min_m if metric else None,
            distance_max_m=metric.distance_max_m if metric else None,
            distance_source=metric.distance_source if metric else "",
            depth_ok=camera_depth_ok(self.camera),
            target_seen=bool(cv_packet and cv_packet.has_dry_target),
            hand_test=self.hand_test,
            sitl=self.sitl,
            vel_body=vel,
            gimbal_pwm=gimbal_pwm,
        )

    def _handle_safety_abort(self, abort: SafetyAbort) -> None:
        print(f"[SAFETY] Mission abort: {abort.reason}")
        self.send_hud_message(f"ABORT {abort.reason}"[:50])
        if not self.sim or self.sitl:
            self.nav.stop()
            if abort.trigger_rtl:
                send_rtl(self.master)
                print("[SAFETY] RTL commanded")
        self.set_state(STATE_ABORTED)

    def _handle_target_lost(self) -> bool:
        if self.frames_without_target <= self.max_frames_without_target:
            return False
        if self.state not in (STATE_APPROACHING, STATE_AIMING):
            return False
        print(f"Target lost for {self.max_frames_without_target} frames")
        if not self.sim or self.sitl:
            self.nav.stop()
        self.set_state(STATE_SEARCHING)
        return True

    def _metric_hud(self, metric: MetricPacket) -> str:
        if metric.distance_min_m is not None and metric.distance_max_m is not None:
            dist = f"{metric.distance_min_m:.1f}-{metric.distance_max_m:.1f}m"
        elif metric.distance_m is not None:
            dist = f"{metric.distance_m:.1f}m"
        else:
            dist = "?"
        return f"LOCK dist={dist} src={metric.distance_source or '?'}"

    def _allow_motion(self) -> bool:
        return (not self.sim or self.sitl) and not self.hand_test

    def _spray_enabled(self) -> bool:
        method = str(self.cfg.get("spray", {}).get("method", "MAVLINK_SERVO")).lower()
        return method not in ("none", "")

    def _aim_gimbal(self, hit, frame_h: int) -> None:
        if not self.gimbal.enabled or hit is None:
            return
        self.gimbal.center_pitch(hit.cy, frame_h, send=(not self.sim or self.sitl))

    def loop(self) -> None:
        source = self.cfg.get("camera", {}).get("source", "scrcpy")
        if self.sitl:
            host = "SITL"
        elif source == "rpi_local":
            host = "ONBOARD"
        else:
            host = "GCS"
        print(f"\n=== {host} AUTO-EXTINGUISH ===")
        print(f"CV method: {self.cv_method}")
        if self.sitl:
            print("SITL: ArduPilot sim — motion enabled (arm GUIDED in SITL console)")
        if self.hand_test:
            print("HAND-TEST: props off — no drone velocity/spray; gimbal + perception active")
        print("Pipeline: CV -> MetricRecon -> AutoNav -> Spray -> Upload")
        if host == "GCS":
            print("Waiting for scrcpy window... (Ctrl+C to abort)")
        elif source in ("video", "synthetic"):
            print(f"Replay camera ({source}) active (Ctrl+C to abort)")
        else:
            print("Onboard Pi camera active (Ctrl+C to abort)")

        try:
            while True:
                if self._stop_loop:
                    break
                safety_abort = self.safety.check()
                if safety_abort:
                    self._handle_safety_abort(safety_abort)
                    break

                frame = self.camera.get_frame()
                if frame is None:
                    time.sleep(0.5)
                    continue

                frame_h, frame_w = frame.shape[:2]
                cv_packet = self._run_cv(frame)
                metric = self._run_metric(cv_packet, frame_w, frame_h)
                hit = cv_packet.primary_dry if cv_packet else None
                self._publish_telemetry(cv_packet, metric)

                if hit:
                    self.frames_without_target = 0
                    if metric and time.time() - self.last_hud_alert_time > 1.5:
                        self.send_hud_message(self._metric_hud(metric))
                        self.last_hud_alert_time = time.time()
                else:
                    self.frames_without_target += 1

                if self._handle_target_lost():
                    continue

                if not self.headless:
                    overlay = draw_overlay(
                        frame,
                        cv_packet,
                        self.state,
                        metric=metric,
                        show_yolo_crop=self.cv_method in ("yolo", "both"),
                    )
                    cv2.imshow("Valiant Mission View", overlay)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

                if self.state == STATE_SEARCHING:
                    if metric:
                        self.set_state(STATE_APPROACHING)

                elif self.state == STATE_APPROACHING:
                    if time.time() - self.state_start_time > self.approach_timeout_s:
                        self.set_state(STATE_SEARCHING)
                        continue
                    if metric and hit:
                        intent = self.planner.intent_for_approaching(metric)
                        if intent == MotionIntent.ABORT:
                            print("[Nav] Abort - insufficient side clearance")
                            if not self.sim or self.sitl:
                                self.nav.stop()
                            self.set_state(STATE_SEARCHING)
                            continue
                        if self.planner.should_switch_to_aiming(metric, hit.area):
                            self.set_state(STATE_AIMING)
                            continue
                        self._aim_gimbal(hit, frame_h)
                        if not self._allow_motion() and intent == MotionIntent.APPROACH:
                            pass
                        elif self._allow_motion() and intent == MotionIntent.APPROACH:
                            self.nav.move_toward_target(
                                metric, frame_w, frame_h,
                                approach_speed=self.approach_speed,
                                camera_down=self.camera_down,
                            )

                elif self.state == STATE_AIMING:
                    if time.time() - self.state_start_time > self.lock_timeout_s:
                        self.set_state(STATE_SEARCHING)
                        continue
                    if metric:
                        intent = self.planner.intent_for_aiming(metric)
                        if intent == MotionIntent.ABORT:
                            if not self.sim or self.sitl:
                                self.nav.stop()
                            self.set_state(STATE_SEARCHING)
                            continue
                        if not self._allow_motion():
                            pass
                        else:
                            self.nav.hold_center(
                                metric, frame_w, frame_h, camera_down=self.camera_down
                            )
                        self._aim_gimbal(hit, frame_h)
                        if is_aimed(metric, self.cfg):
                            if self.lock_start_time is None:
                                self.lock_start_time = time.time()
                            elif time.time() - self.lock_start_time >= self.lock_duration_s:
                                if self.planner.can_fire(metric, lock_duration_met=True):
                                    if self._allow_motion():
                                        self.nav.stop()
                                    if self.hand_test:
                                        print("[HAND-TEST] Would fire here (spray skipped)")
                                        self.set_state(STATE_SEARCHING)
                                    elif not self._spray_enabled():
                                        self.confirm_frame = frame
                                        self.set_state(STATE_CAPTURING)
                                    else:
                                        self.set_state(STATE_FIRING)
                                else:
                                    print("[Spray] Aim lock met but approach-from-2m not validated")
                        else:
                            self.lock_start_time = None

                elif self.state == STATE_FIRING:
                    if self.hand_test:
                        self.set_state(STATE_SEARCHING)
                        continue
                    if metric and not is_aimed(metric, self.cfg):
                        print("[Spray] Fire aborted - lost aim")
                        self.set_state(STATE_AIMING)
                        continue
                    print(f"Firing water for {self.shoot_duration_s}s (target {self.target_number})")
                    self.trigger.fire(self.shoot_duration_s)
                    self.confirm_frame = None
                    if self.require_shot:
                        self.set_state(STATE_VERIFYING)
                    else:
                        self.confirm_frame = frame
                        self.set_state(STATE_CAPTURING)

                elif self.state == STATE_VERIFYING:
                    elapsed = time.time() - self.state_start_time
                    if elapsed > self.shot_confirm_timeout_s:
                        print("[CONOPS] Shot confirmation timeout - no blue/wet target detected")
                        self.set_state(STATE_SEARCHING)
                        continue
                    if elapsed < self.post_spray_settle_s:
                        continue
                    if has_shot_confirmation(cv_packet):
                        self.confirm_frame = frame
                        print("[CONOPS] Shot target confirmed in frame")
                        self.set_state(STATE_CAPTURING)

                elif self.state == STATE_CAPTURING:
                    if self.confirm_frame is not None:
                        os.makedirs(self.photo_save_dir, exist_ok=True)
                        filename = task2_photo_filename(self.cfg, self.target_number)
                        self.upload_file_path = os.path.join(self.photo_save_dir, filename)
                        cv2.imwrite(self.upload_file_path, self.confirm_frame)
                        print(f"Saved: {self.upload_file_path}")
                        self.set_state(STATE_UPLOADING)
                    else:
                        self.set_state(STATE_SEARCHING)

                elif self.state == STATE_UPLOADING:
                    if self.upload_file_path:
                        ok = self.uploader.upload_task2_photo(
                            self.upload_file_path,
                            self.target_number,
                        )
                        if ok:
                            self.targets_completed += 1
                            self.send_hud_message(
                                f"Target {self.target_number} uploaded"
                            )
                    self.target_number += 1
                    if self.max_targets is not None and self.targets_completed >= self.max_targets:
                        self.set_state(STATE_COMPLETE)
                    else:
                        print(
                            f"[CONOPS] Target {self.target_number - 1} done. "
                            f"Searching for next target..."
                        )
                        self.set_state(STATE_SEARCHING)

                elif self.state == STATE_COMPLETE:
                    print(
                        f"Task 2 sequence complete. "
                        f"Extinguished {self.targets_completed} target(s)."
                    )
                    break

                elif self.state == STATE_ABORTED:
                    break

        except KeyboardInterrupt:
            print("\nAborted by user.")
        finally:
            if self._allow_motion():
                self.nav.stop()
            self.metric_recon.stop()
            self.trigger.cleanup()
            self.gimbal.cleanup()
            self.camera.cleanup()
            if self._telemetry is not None:
                self._telemetry.close()
            cv2.destroyAllWindows()


def run_auto_extinguish(
    *,
    connection: str | None = None,
    baud: int | None = None,
    sim: bool = False,
    sitl: bool = False,
    headless: bool = False,
    phone_ip: str | None = None,
    max_targets: int | None = None,
    hand_test: bool = False,
    gcs_ip: str | None = None,
    profile: str | None = None,
    video_path: str | None = None,
    scenario_path: str | None = None,
) -> None:
    cfg = load_config("vion")
    if profile:
        from valiant.autonomy.flight.profile import apply_flight_profile

        cfg = apply_flight_profile(cfg, profile)
    if scenario_path:
        cfg.setdefault("camera", {})["source"] = "synthetic"
        cfg["camera"]["synthetic_scenario"] = scenario_path
    if sitl:
        cfg.setdefault("camera", {})
        if not video_path and not scenario_path:
            if cfg["camera"].get("source") == "scrcpy":
                cfg["camera"]["source"] = "synthetic"
                cfg["camera"].setdefault(
                    "synthetic_scenario", "tests/fixtures/sitl_approach.json"
                )
    mavlink_cfg = cfg.get("mavlink", {})
    if connection:
        conn = connection
    elif sitl:
        conn = mavlink_cfg.get("sitl_connection", "tcp:127.0.0.1:5760")
    elif cfg.get("camera", {}).get("source") == "rpi_local":
        conn = mavlink_cfg.get("rpi_connection", "/dev/ttyAMA0")
    else:
        conn = mavlink_cfg.get("connection", "udpin:127.0.0.1:14550")
    baud_rate = baud if baud is not None else mavlink_cfg.get("baud", 57600)
    monitor_ip = gcs_ip or cfg.get("gcs_monitor", {}).get("ip")
    if sitl and not monitor_ip:
        monitor_ip = "127.0.0.1"

    extinguisher = AutoExtinguisher(
        cfg,
        connection_string=conn,
        baudrate=baud_rate,
        sim_mode=sim,
        sitl_mode=sitl,
        headless=headless,
        phone_ip=phone_ip,
        max_targets=max_targets,
        hand_test=hand_test,
        gcs_ip=monitor_ip,
        video_path=video_path,
    )
    extinguisher.loop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Vion Task 2 autonomous fire extinguishing")
    parser.add_argument("--connection", default=None)
    parser.add_argument("--baud", type=int, default=None)
    parser.add_argument("--sim", action="store_true", help="Dry-run: no MAVLink motion")
    parser.add_argument("--sitl", action="store_true", help="ArduPilot SITL (tcp:5760, motion on)")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--scrcpy-ip", default=None)
    parser.add_argument("--video", default=None, help="Video file for replay camera")
    parser.add_argument("--scenario", default=None, help="Synthetic target JSON scenario")
    parser.add_argument(
        "--max-targets",
        type=int,
        default=None,
        help="Stop after N targets (default: unlimited per conops.yaml)",
    )
    parser.add_argument(
        "--hand-test",
        action="store_true",
        help="Props-off bench: perception + MAVLink + GCS monitor only",
    )
    parser.add_argument("--gcs-ip", default=None, help="GCS laptop IP for telemetry mirror")
    parser.add_argument("--profile", default=None, help="Flight profile overlay (e.g. vivi)")
    args = parser.parse_args()
    if args.sim and args.sitl:
        parser.error("--sim and --sitl are mutually exclusive")
    run_auto_extinguish(
        connection=args.connection,
        baud=args.baud,
        sim=args.sim,
        sitl=args.sitl,
        headless=args.headless,
        phone_ip=args.scrcpy_ip,
        max_targets=args.max_targets,
        hand_test=args.hand_test,
        gcs_ip=args.gcs_ip,
        profile=args.profile,
        video_path=args.video,
        scenario_path=args.scenario,
    )


if __name__ == "__main__":
    main()
