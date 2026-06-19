# Field Test Plan - AEAC2027

Phased validation from bench to competition. Each phase has pass criteria before moving up. Log results in a shared spreadsheet or GitHub issue comments.

**Prerequisites for all outdoor tests:** FRR-approved airframe, spotter, geofence loaded, emergency RC switch tested, water refill plan.

---

## Phase 0 - Bench (no drone)

**Goal:** Software and perception work on a laptop only.

| # | Test | Command / action | Pass criteria |
|---|------|------------------|---------------|
| 0.1 | Environment | `python tools\verify_env.py` | All required packages OK |
| 0.2 | CONOPS config | `python tools\conops_check.py` | PASSED |
| 0.3 | Safety logic | `python tools\safety_bench_test.py` | Battery, geofence, timeout aborts |
| 0.4 | CV dry detection | `python tools\valiant.py bench cv --camera 0` | Purple dry targets boxed on synthetic or printed circles |
| 0.5 | CV shot detection | Wet a blue test circle, run bench cv | Shot list populates after wetting |
| 0.6 | Metric pipeline (3D) | `python tools\valiant.py bench metric --camera 0` | distance_m, horizontal_range_m, altitude_error_m print steadily |
| 0.7 | Sim orchestrator | `python missions\task2_vion_auto_extinguish.py --sim --max-targets 1` | State machine reaches VERIFYING or COMPLETE without crash |
| 0.8 | SITL closed loop | WSL: `.\tools\launch_sitl.ps1`; then `.\tools\run_sitl_mission.ps1 -Profile sitl` | Monitor shows APPROACHING; SITL armed GUIDED; velocity non-zero when target off-centre |

See [sitl-wsl.md](sitl-wsl.md) for WSL ArduPilot setup.

**Known gaps at Phase 0:** HSV thresholds are synthetic-first. Outdoor lighting will need retuning (see GitHub issue CV-refinement).

---

## Phase 1 - GCS link + actuation (drone tethered or props off)

**Goal:** MAVLink, spray servo, and Pi companion link work with Vion powered but not flying.

Bringup checklist: [vion-bringup.md](vion-bringup.md)

| # | Test | Setup | Pass criteria |
|---|------|-------|---------------|
| 1.1 | Telemetry | Mission Planner + telemetry radio COM @ 57600 | Heartbeat, GUIDED_NOGPS selectable (indoor) |
| 1.2 | Pi MAVLink | `check_sensors.py` on Pi | Heartbeat on `/dev/ttyAMA0` |
| 1.3 | STATUSTEXT HUD | Pi `run_mission.py --sim` | T2: messages in MP HUD |
| 1.4 | Spray servo | MP servo test or orchestrator | SERVO15 opens/closes |
| 1.5 | H-Flow | MP status, bench hover | `opt_qua` reasonable on venue floor |
| 1.6 | Depth cal | Pi capture 1/2/3 m; GCS `validate_calibration.py` | Within 10% gate |
| 1.7 | GCS monitor | Pi `--gcs-connection udpout:<LAPTOP_IP>:14550` | `mission_monitor.py` shows GOOD |

---

## Phase 2 - Hover / slow approach (manual pilot + auto nav)

**Goal:** Auto-nav velocity commands behave safely with a human on the sticks ready to override.

Run on Pi: `python hardware/vion/rpi/run_mission.py --profile indoor`

| # | Test | Setup | Pass criteria |
|---|------|-------|---------------|
| 2.1 | Velocity stop | Ctrl+C during APPROACHING | Zero velocity command on exit |
| 2.2 | Center hold | AIMING on a fixed printed target at 1-2 m | Drone holds target near frame centre without oscillation |
| 2.3 | Approach from 2 m+ | Start beyond 2 m, `--max-targets 1` | Planner `approach_valid` true before fire gate |
| 2.4 | Side clearance abort | Target near frame edge | ABORT, return to SEARCHING, no lateral creep into obstacle |
| 2.5 | Target loss | Occlude target 1+ sec | Revert to SEARCHING, nav stop |
| 2.6 | Safety battery | Simulate low battery in SITL or bench inject | Mission abort, optional RTL |

**Tuning knobs:** `auto_nav.kp_x/y`, `deadband_px`, `approach_speed`, `side_clearance_m`

---

## Phase 3 - Full autonomous cycle (single target)

**Goal:** One complete CONOPS cycle: detect, approach, aim, fire, verify shot, photo, upload.

| # | Test | Setup | Pass criteria |
|---|------|-------|---------------|
| 3.1 | Dry detect outdoors | Purple paper target, outdoor light | CV dry hit stable 10+ frames |
| 3.2 | Full auto single | `--max-targets 1`, real spray | Water hits target, VERIFYING sees shot colour |
| 3.3 | Photo naming | Check `task2_photos/` | `Task_2_{team}_target_1.jpg` exists |
| 3.4 | Upload | `--upload` or default uploader | File in `uploaded/` or Google Drive |
| 3.5 | Judge workflow | Operator declares to judge, show photo on laptop | Matches CONOPS real-time confirmation |
| 3.6 | 2 m approach proof | Review logs / HUD distance | max distance seen >= 2 m before fire |

**Fail common causes:** HSV false negatives outdoors, shot confirmation timeout, aim lock too tight, spray duration too short.

---

## Phase 4 - Multi-target flight window

**Goal:** Repeat Phase 3 for multiple targets with water refill between runs.

| # | Test | Setup | Pass criteria |
|---|------|-------|---------------|
| 4.1 | Target 1 then 2 | Two spaced targets, no `--max-targets` | target_1 and target_2 photos numbered in order |
| 4.2 | Refill between | Empty tank mid-window | Manual refill, resume SEARCHING |
| 4.3 | Manual fallback | Kill auto, run manual_photo scrcpy | Backup photos + upload work |
| 4.4 | Mission timeout | Optional shorten `safety.mission_timeout_s` for test | Clean abort |

---

## Phase 5 - Task 1 (Vivi)

**Goal:** Building survey and target report in field conditions.

| # | Test | Setup | Pass criteria |
|---|------|-------|---------------|
| 5.1 | Corner capture | `task1_vivi_survey.py` setup phase | A/B/C model builds without collinear error |
| 5.2 | Target localization | Fly to known target positions | Report descriptions unambiguous per CONOPS |
| 5.3 | Report upload | End of window | `Task_1_{team}_targets.txt` on Google Drive |

---

## Phase 6 - Competition rehearsal

**Goal:** Full flight window simulation under time pressure.

Use [competition-day.md](competition-day.md) checklist. Run Phase 3+4 back-to-back with judges observing.

| Role | Person |
|------|--------|
| Pilot | Manual override authority |
| GCS operator | Runs orchestrator, declares targets |
| Spotter | Visual line of sight |
| Photo/upload checker | Confirms Drive folder during window |

---

## Open engineering items (whiteboard gaps)

These are tracked as GitHub issues. Highest priority before Phase 3:

1. **CV refinement** - outdoor HSV tuning, false positive rejection, optional YOLO ONNX models
2. **Metric recon calibration** - FOV vs VL53L1X agreement, target diameter range 5-30 cm
3. **Auto-nav tuning** - PD gains for real approach, no oscillation near target
4. **Spray aim hardware** - body-frame velocity vs physical nozzle aim if 2-axis gimbal added
5. **Real Google Drive upload** - service account + folder_id for competition
6. **Autonomous takeoff/landing** - 5+5 pts scoring (optional, not in orchestrator yet)

---

## Result log template

Copy per test session:

```
Date:
Location:
Phase:
Tester:
Config git SHA:
vion.yaml COM port:
cv.method:
metric_recon.rangefinder:

Test ID | Pass/Fail | Notes
0.4     |           |
...

Blockers for next phase:
```
