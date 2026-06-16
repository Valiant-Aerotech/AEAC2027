"""Task 2 state machine - CV -> Metric Recon -> Auto-Nav -> Spray -> Upload."""

from __future__ import annotations

import argparse
import math
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
from valiant.common.mavlink import (
    connect,
    request_sitl_telemetry_streams,
    request_sys_status_stream,
    send_gcs_heartbeat,
    send_rtl,
    send_statustext,
)

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
        skip_sitl_preflight: bool = False,
    ):
        self.cfg = cfg
        self.sim = sim_mode
        self.sitl = sitl_mode
        self.headless = headless
        self.hand_test = hand_test
        self._skip_sitl_preflight = skip_sitl_preflight
        self._sitl_preflight_done = False
        self._last_gcs_heartbeat = 0.0
        self._last_pose_log = 0.0
        self._last_guided_check = 0.0
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
            if sitl_mode:
                request_sitl_telemetry_streams(self.master)

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
        self._sitl_pose = None
        self._sitl_map = None
        self._sitl_map_view_radius = 24.0
        if self.sitl:
            from valiant.common.sitl_map_asset import SitlMapAsset
            from valiant.common.sitl_physics import VehiclePose

            map_cfg = cfg.get("sitl", {}).get("map", {})
            manifest = map_cfg.get("manifest")
            if manifest:
                self._sitl_map = SitlMapAsset.load(manifest)
                if self._sitl_map is None:
                    print(f"[SITL] Map not found ({manifest}) — run: python tools/download_sitl_map.py")
                else:
                    print(f"[SITL] Satellite map loaded ({manifest})")
            self._sitl_map_view_radius = float(map_cfg.get("view_radius_m", 24.0))
            self._sitl_pose = VehiclePose()

    def request_stop(self) -> None:
        self._stop_loop = True

    def send_hud_message(self, message: str) -> None:
        send_statustext(self.master, message, prefix="T2: ")

    def set_state(self, new_state: str) -> None:
        if self.state != new_state:
            if new_state == STATE_SEARCHING and self.state in (STATE_APPROACHING, STATE_AIMING):
                self._sitl_stop_motion()
            msg = f"STATE: {self.state} -> {new_state}"
            print(f">>> {msg}")
            self.send_hud_message(msg)
            self.state = new_state
            self.state_start_time = time.time()
            if new_state == STATE_SEARCHING:
                self.lock_start_time = None
                self.planner.reset_approach()
                if self.gimbal.enabled and (not self.sim or self.sitl):
                    self.gimbal.reset()
            if new_state == STATE_APPROACHING:
                self.planner.reset_approach()
                if self.sitl and self._allow_motion():
                    self.nav.start_velocity_stream()

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
        extra = None
        if self.sitl and self._sitl_pose is not None and self._sitl_pose.ok:
            extra = {
                "pos_x": round(self._sitl_pose.x, 2),
                "pos_y": round(self._sitl_pose.y, 2),
                "alt_m": round(-self._sitl_pose.z, 2),
            }
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
            extra=extra,
        )

    def _sitl_stop_motion(self) -> None:
        if not self._allow_motion():
            return
        self.nav.stop()

    def _handle_safety_abort(self, abort: SafetyAbort) -> None:
        print(f"[SAFETY] Mission abort: {abort.reason}")
        self.send_hud_message(f"ABORT {abort.reason}"[:50])
        if not self.sim or self.sitl:
            self._sitl_stop_motion()
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

    def _refresh_sitl_pose(self) -> None:
        if not self.sitl or self._sitl_pose is None:
            return
        from valiant.common.sitl_physics import drain_vehicle_pose

        self._sitl_pose = drain_vehicle_pose(self.master, self._sitl_pose)

    def _ensure_sitl_guided(self) -> None:
        if not self.sitl or self.hand_test:
            return
        now = time.time()
        if now - self._last_guided_check < 2.0:
            return
        self._last_guided_check = now
        mode = self.master.flightmode
        if mode == "GUIDED":
            return
        print(f"[SITL] FC mode is {mode!r} — re-commanding GUIDED")
        mapping = self.master.mode_mapping()
        if "GUIDED" not in mapping:
            return
        self.master.set_mode(mapping["GUIDED"])

    def _actual_vel_body(self) -> tuple[float, float, float] | None:
        if not self.sitl or self._sitl_pose is None or not self._sitl_pose.ok:
            return None
        pose = self._sitl_pose
        cy, sy = math.cos(pose.yaw), math.sin(pose.yaw)
        vx = pose.vx * cy + pose.vy * sy
        vy = -pose.vx * sy + pose.vy * cy
        return (vx, vy, pose.vz)

    def _overlay_velocities(self) -> tuple[tuple[float, float, float] | None, tuple[float, float, float] | None]:
        if not self._allow_motion():
            return None, None
        cmd = self.nav.servo.last_vel_body
        return cmd, self._actual_vel_body()

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
        if self.sitl and not self._sitl_preflight_done:
            print("[SITL] ArduPilot sim — motion enabled (preflight in loop)")
        if self.hand_test:
            print("HAND-TEST: props off — no drone velocity/spray; gimbal + perception active")
        print("Pipeline: CV -> MetricRecon -> AutoNav -> Spray -> Upload")
        if self.sitl and not self.hand_test and not self._sitl_preflight_done:
            if not self._skip_sitl_preflight:
                from valiant.autonomy.sitl_preflight import arm_guided_takeoff

                takeoff_alt = float(self.cfg.get("sitl", {}).get("takeoff_alt_m", 3.0))
                preflight_timeout = float(self.cfg.get("sitl", {}).get("preflight_timeout_s", 75.0))
                ekf_wait = float(self.cfg.get("sitl", {}).get("ekf_wait_s", 60.0))
                arm_guided_takeoff(
                    self.master,
                    takeoff_alt_m=takeoff_alt,
                    timeout_s=preflight_timeout,
                    ekf_wait_s=ekf_wait,
                )
                request_sitl_telemetry_streams(self.master)
                send_gcs_heartbeat(self.master)
            else:
                print("[SITL] Skipping preflight (assume already armed/airborne)")
            self._sitl_preflight_done = True
        if self.sitl and not self.hand_test:
            self.nav.start_velocity_stream()
        if host == "GCS":
            print("Waiting for scrcpy window... (Ctrl+C to abort)")
        elif source in ("video", "synthetic", "synthetic_physics"):
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

                if self.sitl and time.time() - self._last_gcs_heartbeat > 1.0:
                    send_gcs_heartbeat(self.master)
                    self._last_gcs_heartbeat = time.time()

                if self.state in (STATE_APPROACHING, STATE_AIMING):
                    self._ensure_sitl_guided()

                self._refresh_sitl_pose()
                if (
                    self.sitl
                    and self._sitl_pose is not None
                    and self._sitl_pose.ok
                    and time.time() - self._last_pose_log > 2.0
                ):
                    p = self._sitl_pose
                    print(
                        f"[SITL] pos N={p.x:.2f} E={p.y:.2f} alt={-p.z:.2f}m "
                        f"vel_n={p.vx:.2f}"
                    )
                    self._last_pose_log = time.time()
                if self._sitl_pose is not None and self._sitl_pose.ok:
                    self.nav.servo.set_yaw_rad(self._sitl_pose.yaw)
                if hasattr(self.camera, "set_vehicle_pose") and self._sitl_pose is not None and self._sitl_pose.ok:
                    self.camera.set_vehicle_pose(self._sitl_pose)
                if hasattr(self.camera, "set_gimbal_pwm"):
                    self.camera.set_gimbal_pwm(self.gimbal.current_pwm)
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

                if self.state in (STATE_APPROACHING, STATE_AIMING) and not hit:
                    self._sitl_stop_motion()

                if (
                    hasattr(self.camera, "gimbal_pwm_hint")
                    and self._sitl_pose is not None
                    and self._sitl_pose.ok
                    and self.gimbal.enabled
                    and self.state in (STATE_SEARCHING, STATE_APPROACHING)
                    and (self.state == STATE_SEARCHING or hit is None)
                ):
                    hint = self.camera.gimbal_pwm_hint(self._sitl_pose)
                    if hint is not None:
                        self.gimbal.command_pwm(hint, send=(not self.sim or self.sitl))

                if self._handle_target_lost():
                    continue

                if not self.headless:
                    vel_cmd, vel_sim = self._overlay_velocities()
                    overlay = draw_overlay(
                        frame,
                        cv_packet,
                        self.state,
                        metric=metric,
                        show_yolo_crop=self.cv_method in ("yolo", "both"),
                        vel_cmd_body=vel_cmd,
                        vel_actual_body=vel_sim,
                    )
                    cv2.imshow("Valiant Mission View", overlay)
                    if hasattr(self.camera, "world_scene") and self._sitl_pose is not None:
                        from valiant.autonomy.cv.sitl_map_view import (
                            render_topdown,
                            render_wall_side,
                        )

                        scene = self.camera.world_scene
                        top = render_topdown(
                            scene,
                            self._sitl_pose,
                            vel_cmd=vel_cmd,
                            map_asset=self._sitl_map,
                            view_radius_m=self._sitl_map_view_radius,
                        )
                        side = render_wall_side(scene, self._sitl_pose)
                        cv2.imshow("SITL Top-Down", top)
                        cv2.imshow("SITL Wall View", side)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

                if self.state == STATE_SEARCHING:
                    if metric and hit:
                        self.set_state(STATE_APPROACHING)

                elif self.state == STATE_APPROACHING:
                    if time.time() - self.state_start_time > self.approach_timeout_s:
                        self.set_state(STATE_SEARCHING)
                        continue
                    if metric and hit:
                        if self.planner.should_switch_to_aiming(metric, hit.area):
                            self.set_state(STATE_AIMING)
                            continue
                        intent = self.planner.intent_for_approaching(metric, bbox_area=hit.area)
                        if intent == MotionIntent.ABORT:
                            print("[Nav] Abort - insufficient side clearance")
                            self._sitl_stop_motion()
                            self.set_state(STATE_SEARCHING)
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
                        intent = self.planner.intent_for_aiming(metric, bbox_area=hit.area if hit else 0)
                        if intent == MotionIntent.ABORT:
                            self._sitl_stop_motion()
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
                                    self._sitl_stop_motion()
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
            self._sitl_stop_motion()
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
    skip_sitl_preflight: bool = False,
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
        conn = (
            mavlink_cfg.get("sitl_connection")
            or mavlink_cfg.get("connection")
            or "tcp:127.0.0.1:5760"
        )
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
        skip_sitl_preflight=skip_sitl_preflight,
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
    parser.add_argument(
        "--skip-sitl-preflight",
        action="store_true",
        help="Skip SITL arm/takeoff (already airborne)",
    )
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
        skip_sitl_preflight=args.skip_sitl_preflight,
    )


if __name__ == "__main__":
    main()
