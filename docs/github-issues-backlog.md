# GitHub Issues Backlog

Use `tools/dev/create_github_issues.ps1` to create issues on [Valiant-Aerotech/AEAC2027](https://github.com/Valiant-Aerotech/AEAC2027).

```powershell
gh auth login
.\tools\dev\create_github_issues.ps1
```

**Branch workflow:** create a feature branch off `main`, push the branch, open a PR into `main`. See [branches.md](branches.md).

**Dev tools:** `python tools/valiant.py guide` - index in [tools/README.md](../tools/README.md). First run: [START_HERE.md](../START_HERE.md).

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

Merged **PR #85** (`cv-metric-integration`) to `main`.

| Area | Status |
|------|--------|
| **CV public API** | `valiant.autonomy.cv` facade: `create_target_detector`, `draw_mission_overlay`, `hits_to_bench_dict`; subframe YOLO (294px spiral); import boundaries in `test_subsystem_boundaries.py` |
| **Edge clearance** | L/R/T/B `EdgeProximity`, 2D virtual aim, planner bypass + fire gates, dual spray alignment, HUD edge labels; SITL ceiling constraint |
| **Subsystem APIs** | `metric_recon/api.py`, `auto_nav/api.py`, `spray/api.py`; orchestrator uses public imports only |
| **Docs** | `interfaces.md` CV methods + MetricPacket edge fields; field-test-plan drills 2.4b–d |
| **Tests** | 223 passed in `tests/` (edge, aim, spray, ceiling, cv_api, public_apis) |

## Recent progress (2026-06-19)

| Area | Status |
|------|--------|
| **SITL GCS HUD** | `T2:` STATUSTEXT in Mission Planner Messages; human-readable state lines; `gcs verify-statustext` |
| **SITL pattern flight** | `sitl pattern`: GUIDED box (10 m / turns / LOITER); yaw via SET_POSITION_TARGET mask 2503 at 20 Hz |
| **Vivi orbit (GUIDED)** | `sitl orbit` / `field orbit`; circle R=5 m, LOITER handoff; SITL validate then Vivi field |
| **WSL / tools paths** | `wsl_distro.ps1`, `diagnostics.ps1`, `audit_script_paths.py`; diagnose checklist |
| **3D motion (SITL)** | `ned_kinematics.py`, world-primary motion, search creep with descent |
| **3D metric recon** | `MetricPacket` slant/horizontal range, `geometry_3d.py`, altitude alignment gates |
| **Tools** | `tools/valiant.py` CLI; `sitl run`, `sitl pattern`, `sitl orbit`, `field orbit`, `gcs verify-statustext` |
| **Tests** | 100+ unit tests including `test_field_orbit`, `test_gcs_hud`, `test_visual_servo_guided`, `test_sitl_pattern` |

### Closed on create (done in repo)

Tracks A1-A7, B1-B8, C1-C7, C9, C13, D1-D9 (code), D15-D16, E1, E5-E6, E7-E9, F1-F4, F6

C13: CV public API + subframe YOLO (#86, PR 85)  
D15: Edge clearance four edges (#87, PR 85)  
D16: Subsystem public API facades (#88, PR 85)

E7: SITL Mission Planner STATUSTEXT (GCS HUD)  
E8: SITL guided box pattern flight  
E9: Script path audit and WSL distro fixes  

### Open - refinement and field test (priority order)

| Issue | GH | Track | Priority | Module | Repo status (2026-06-19) |
|-------|-----|-------|----------|--------|------------------------|
| Full pipeline field test - single target (Phase 3) | #70 | E | high | field-test | **SITL pass** + PR #85 CV/edge; outdoor/Vivi bench pending |
| Outdoor HSV tuning for dry/shot targets | #21 | C | high | cv | open; YOLO dry primary; HSV for shot + fallback |
| Shot detection after real spray | #23 | C | high | cv | open; needs wet target on hardware |
| Train/export dry + shot ONNX models | #19 | C | medium | cv | **partial**; subframe dry path; `shot.onnx` missing |
| CV regression set from recorded footage | #22 | C | medium | cv | open; public API + `getTargets()` parity (PR #85) |
| Depth sensor field validation (ArduCam + H-Flow) | #26 | D | high | metric-recon | **partial**; edge depth-jump sampling (PR #85); hardware pending |
| FOV / depth calibration vs tape measure | #27 | D | medium | metric-recon | **partial**; `valiant calibrate validate` |
| Auto-nav PD gain tuning (no oscillation) | #28 | D | high | auto-nav | **partial**; edge bypass + `servo_px` (PR #85); field tune pending |
| Side clearance calibration with real scene | #29 | D | medium | auto-nav | **partial**; edge code on `main` (PR #85); drills 2.4b–d field pending |
| Real Google Drive upload | #25 | D | high | upload | open; local copy only in dev/SITL |
| Multi-target flight window test (Phase 4) | #71 | E | high | field-test | **deprioritized**; single-target daily driver |
| Target-loss recovery on real feed | #73 | E | medium | cv | **partial**; SITL remediation; field CV latency TBD |
| scrcpy latency field tuning | #72 | E | medium | infra | deprioritized; RPi primary path |
| Roadmap phases 0-6 | #78 | - | high | field-test | Phase 0-2 + edge clearance SITL ready (PR #85); 3-6 need hardware |
| GitHub Projects board + recruit welcome | #8 | A | medium | infra | open; WELCOME/ONBOARDING/tools README updated |
| Task 1 Vivi field test (Phase 5) | #77 | - | medium | task1 | open |
| Autonomous takeoff/landing (CONOPS 5+5 pts) | #75 | F | low | auto-nav | open; SITL NAV_TAKEOFF preflight only |
| Adapt config when 2027 CONOPS publishes | #76 | F | low | infra | open |
| Vivi GUIDED orbit field test (Phase E10) | #89 | E | high | field-test | **SITL path in repo**; outdoor Vivi pending |
| Vivi/Vulcan2 FC Lua + Mission Planner docs | #17 | B | low | infra | open |

See [field-test-plan.md](runbooks/field-test-plan.md). SITL: [sitl-overview.md](runbooks/sitl-overview.md). Interfaces: [interfaces.md](interfaces.md).
