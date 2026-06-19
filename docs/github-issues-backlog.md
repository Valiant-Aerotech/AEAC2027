# GitHub Issues Backlog

Use `tools/create_github_issues.ps1` to create issues on [Valiant-Aerotech/AEAC2027](https://github.com/Valiant-Aerotech/AEAC2027).

```powershell
gh auth login
.\tools\create_github_issues.ps1
```

**Branch:** develop on **`main`**. See [branches.md](branches.md).

**Dev tools:** `python tools/valiant.py guide` — index in [tools/README.md](../tools/README.md). First run: [START_HERE.md](../START_HERE.md).

## Labels

| Label | Use |
|-------|-----|
| `track-a` ... `track-f` | Which roadmap track |
| `done` | Implemented in repo - issue closed for history |
| `field-test` | Needs outdoor / flight validation |
| `refinement` | Works on bench/SITL, needs field tuning |
| `cv` / `metric-recon` / `auto-nav` / `spray` / `upload` / `task1` / `infra` | Module area |
| `priority-high` | Blocks competition readiness |

## Milestones

- Track A - Foundation
- Track B - Migration
- Track C - CV Module
- Track D - Metric Recon + Auto-Nav + Spray
- Track E - Hardening
- Track F - CONOPS
- Field Test - Ongoing validation

## Recent progress (2026-06-18)

| Area | Status |
|------|--------|
| **3D motion (SITL)** | `ned_kinematics.py`: rotation matrices, unified 3D velocity toward target; search creep includes descent; world-primary motion + pixel lateral fine-tune |
| **3D metric recon** | `MetricPacket`: slant/horizontal range, altitude_error_m, vertical clearance; `geometry_3d.py`; depth bbox + RGB→depth calibration remap |
| **Auto-nav** | Fire/aim gated on altitude alignment; onboard Pi commands vz from altitude_error_m; planner uses horizontal range |
| **Tools** | Unified `tools/valiant.py` CLI; removed `run_monitor.ps1`, `download_sitl_map.ps1`, `setup_gcs.ps1`, `yolo_webcam_test.py`, `cv_regression_test.py` |
| **SITL single-target** | Full loop SEARCHING → COMPLETE; altitude align at AIMING |
| **Dry YOLO** | `models/best.onnx`; orchestrator `cv.method: yolo` |
| **Tests** | `test_ned_kinematics.py`, `test_metric_geometry_3d.py`; 39+ motion/metric unit tests passing |
| **Field / hardware** | Phase 3+ still needs Vivi bench tape-measure validation of 3D metrics |

### Closed on create (done in repo)

Tracks A1-A7, B1-B8, C1-C7, C9, D1-D9 (code), E1, E5, E6, F1-F4, F6

### Open - refinement and field test (priority order)

| Issue | GH | Track | Priority | Module | Repo status (2026-06-18) |
|-------|-----|-------|----------|--------|------------------------|
| Full pipeline field test - single target (Phase 3) | #70 | E | high | field-test | **SITL pass** with 3D motion + metric; outdoor/Vivi bench pending |
| Outdoor HSV tuning for dry/shot targets | #21 | C | high | cv | open; YOLO primary; use `valiant bench cv` |
| Shot detection after real spray | #23 | C | high | cv | open; needs wet target on hardware |
| Train/export dry + shot ONNX models | #19 | C | medium | cv | **partial**; `best.onnx` dry; shot ONNX missing |
| CV regression set from recorded footage | #22 | C | medium | cv | open; `valiant bench cv --regression` |
| Depth sensor field validation (ArduCam + H-Flow) | #26 | D | high | metric-recon | **partial**; 3D recon + cal tools on `main`; hardware pass pending |
| FOV / depth calibration vs tape measure | #27 | D | medium | metric-recon | **partial**; slant vs horizontal in recon; `valiant calibrate validate` |
| Auto-nav PD gain tuning (no oscillation) | #28 | D | high | auto-nav | **partial**; 3D motion + lateral_pixel_blend in SITL; field tune pending |
| Side clearance calibration with real scene | #29 | D | medium | auto-nav | **partial**; vertical_clearance_m added; field tune pending |
| Real Google Drive upload | #25 | D | high | upload | open; local copy only in dev/SITL |
| Multi-target flight window test (Phase 4) | #71 | E | high | field-test | **deprioritized**; single-target daily driver |
| Target-loss recovery on real feed | #73 | E | medium | cv | **partial**; SITL remediation + 3D hold; field CV latency TBD |
| scrcpy latency field tuning | #72 | E | medium | infra | deprioritized; RPi primary path |
| Roadmap phases 0-6 | #78 | - | high | field-test | Phase 0-2 SITL + 3D ready; 3-6 need hardware |
| GitHub Projects board + recruit welcome | #8 | A | medium | infra | open; WELCOME/ONBOARDING/tools README updated |
| Task 1 Vivi field test (Phase 5) | #77 | - | medium | task1 | open |
| Autonomous takeoff/landing (CONOPS 5+5 pts) | #75 | F | low | auto-nav | open; SITL NAV_TAKEOFF preflight only |
| Adapt config when 2027 CONOPS publishes | #76 | F | low | infra | open |
| Vivi/Vulcan2 FC Lua + Mission Planner docs | #17 | B | low | infra | open |

See [field-test-plan.md](runbooks/field-test-plan.md). SITL: [sitl-overview.md](runbooks/sitl-overview.md). Interfaces: [interfaces.md](interfaces.md).
