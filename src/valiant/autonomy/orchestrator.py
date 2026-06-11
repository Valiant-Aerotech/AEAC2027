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
    require_shot_confirmation,
    shot_confirm_timeout_s,
    task2_photo_filename,
    validate_conops_config,
)
from valiant.autonomy.safety.monitor import SafetyAbort, SafetyMonitor
from valiant.autonomy.spray.actuation import WaterTrigger
from valiant.autonomy.spray.aim import is_aimed
from valiant.autonomy.upload.drive import DriveUploader
from valiant.common.camera import ScrcpyCamera
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
    """GCS-side autonomous fire extinguishing orchestrator."""

    def __init__(
        self,
        cfg: dict,
        *,
        connection_string: str,
        baudrate: int,
        sim_mode: bool = False,
        headless: bool = False,
        phone_ip: str | None = None,
        max_targets: int | None = None,
    ):
        self.cfg = cfg
        self.sim = sim_mode
        self.headless = headless
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
        self.max_targets = max_targets if max_targets is not None else max_targets_for_window(cfg)
        self.target_number = 1
        self.targets_completed = 0

        for warning in validate_conops_config(cfg):
            print(f"[CONOPS] Warning: {warning}")

        print(f"[INIT] Connecting MAVLink on {connection_string} (sim={sim_mode})...")
        if sim_mode:
            self.master = mavutil.mavlink_connection(connection_string, baud=baudrate)
        else:
            self.master = connect(connection_string, baudrate, wait_heartbeat=True)
            print("[INIT] Heartbeat received")

        if not sim_mode:
            self.master.mav.request_data_stream_send(
                self.master.target_system,
                self.master.target_component,
                mavutil.mavlink.MAV_DATA_STREAM_EXTRA1,
                10,
                1,
            )
            request_sys_status_stream(self.master, rate_hz=2)

        self.nav = MavlinkDriver(self.master, cfg)
        self.safety = SafetyMonitor(self.master, cfg, sim=sim_mode)
        self.planner = MotionPlanner(cfg)
        self.metric_recon = MetricReconstructor(self.master, cfg, sim=sim_mode)
        self.trigger = WaterTrigger(self.master, cfg)
        self.uploader = DriveUploader(cfg)
        self.detector = TargetDetector(cfg)

        self.camera = ScrcpyCamera.from_config(cfg, phone_ip=phone_ip)

        self.state = STATE_SEARCHING
        self.frames_without_target = 0
        self.lock_start_time: float | None = None
        self.state_start_time = time.time()
        self.last_hud_alert_time = 0.0
        self.confirm_frame = None
        self.upload_file_path: str | None = None
        self._last_cv: CVPacket | None = None
        self._last_metric: MetricPacket | None = None

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
        metric = self.metric_recon.reconstruct(cv_packet, frame_w, frame_h)
        self._last_metric = metric
        return metric

    def _handle_safety_abort(self, abort: SafetyAbort) -> None:
        print(f"[SAFETY] Mission abort: {abort.reason}")
        self.send_hud_message(f"ABORT {abort.reason}"[:50])
        if not self.sim:
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
        if not self.sim:
            self.nav.stop()
        self.set_state(STATE_SEARCHING)
        return True

    def _metric_hud(self, metric: MetricPacket) -> str:
        dist = f"{metric.distance_m:.1f}m" if metric.distance_m is not None else "?"
        return f"LOCK dist={dist}"

    def loop(self) -> None:
        print("\n=== GCS AUTO-EXTINGUISH ===")
        print(f"CV method: {self.cv_method}")
        print("Pipeline: CV -> MetricRecon -> AutoNav -> Spray -> Upload")
        print("Waiting for scrcpy window... (Ctrl+C to abort)")

        try:
            while True:
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
                    cv2.imshow("GCS Extinguisher View", overlay)
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
                            if not self.sim:
                                self.nav.stop()
                            self.set_state(STATE_SEARCHING)
                            continue
                        if self.planner.should_switch_to_aiming(metric, hit.area):
                            self.set_state(STATE_AIMING)
                            continue
                        if not self.sim and intent == MotionIntent.APPROACH:
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
                            if not self.sim:
                                self.nav.stop()
                            self.set_state(STATE_SEARCHING)
                            continue
                        if not self.sim:
                            self.nav.hold_center(
                                metric, frame_w, frame_h, camera_down=self.camera_down
                            )
                        if is_aimed(metric, self.cfg):
                            if self.lock_start_time is None:
                                self.lock_start_time = time.time()
                            elif time.time() - self.lock_start_time >= self.lock_duration_s:
                                if self.planner.can_fire(metric, lock_duration_met=True):
                                    if not self.sim:
                                        self.nav.stop()
                                    self.set_state(STATE_FIRING)
                                else:
                                    print("[Spray] Aim lock met but approach-from-2m not validated")
                        else:
                            self.lock_start_time = None

                elif self.state == STATE_FIRING:
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
                    if time.time() - self.state_start_time > self.shot_confirm_timeout_s:
                        print("[CONOPS] Shot confirmation timeout - no blue/wet target detected")
                        self.set_state(STATE_SEARCHING)
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
            if not self.sim:
                self.nav.stop()
            self.metric_recon.stop()
            self.trigger.cleanup()
            self.camera.cleanup()
            cv2.destroyAllWindows()


def run_auto_extinguish(
    *,
    connection: str | None = None,
    baud: int | None = None,
    sim: bool = False,
    headless: bool = False,
    phone_ip: str | None = None,
    max_targets: int | None = None,
) -> None:
    cfg = load_config("vion")
    mavlink_cfg = cfg.get("mavlink", {})
    conn = connection or mavlink_cfg.get("connection", "udpin:127.0.0.1:14550")
    baud_rate = baud if baud is not None else mavlink_cfg.get("baud", 57600)

    extinguisher = AutoExtinguisher(
        cfg,
        connection_string=conn,
        baudrate=baud_rate,
        sim_mode=sim,
        headless=headless,
        phone_ip=phone_ip,
        max_targets=max_targets,
    )
    extinguisher.loop()


def main() -> None:
    parser = argparse.ArgumentParser(description="Vion Task 2 autonomous fire extinguishing")
    parser.add_argument("--connection", default=None)
    parser.add_argument("--baud", type=int, default=None)
    parser.add_argument("--sim", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--scrcpy-ip", default=None)
    parser.add_argument(
        "--max-targets",
        type=int,
        default=None,
        help="Stop after N targets (default: unlimited per conops.yaml)",
    )
    args = parser.parse_args()
    run_auto_extinguish(
        connection=args.connection,
        baud=args.baud,
        sim=args.sim,
        headless=args.headless,
        phone_ip=args.scrcpy_ip,
        max_targets=args.max_targets,
    )


if __name__ == "__main__":
    main()
