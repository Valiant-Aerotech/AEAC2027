# GitHub Issues Backlog

Use `tools/create_github_issues.ps1` to create issues on [Valiant-Aerotech/AEAC2027](https://github.com/Valiant-Aerotech/AEAC2027).

```powershell
gh auth login
.\tools\create_github_issues.ps1
```

**Branch:** develop on **`main`** (onboard-pi + feature/CV merged June 2026). See [branches.md](branches.md).

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

## Recent progress (2026-06)

| Area | Status |
|------|--------|
| **Repo integration** | `main` has Task 2 autonomy, SITL, Pi path, `src/valiant/cv/` scripts (PR #80 + merge `9a4eb43`) |
| **SITL single-target** | Full loop SEARCHING -> COMPLETE on timeline synthetic; spray disabled, photo proof |
| **SITL motion** | Altitude align to target, approach/fire-range fix, COMPLETE hold, dashboard polish |
| **Daily driver** | `.\tools\run_sitl_mission.ps1` (default `--max-targets 1`) |
| **Dry YOLO** | `models/best.onnx` in repo; orchestrator `cv.method: yolo` |
| **Shot ONNX** | Still missing; HSV shot confirmation in loop |
| **Field / hardware** | Phase 3+ still needs Vivi bench and competition hardware |

### Closed on create (done in repo)

Tracks A1-A7, B1-B8, C1-C7, C9, D1-D9 (code), E1, E5, E6, F1-F4, F6

### Open - refinement and field test (priority order)

| Issue | GH | Track | Priority | Module | Repo status (2026-06) |
|-------|-----|-------|----------|--------|------------------------|
| Full pipeline field test - single target (Phase 3) | #70 | E | high | field-test | **SITL pass** on `main`; outdoor/Vivi bench pending |
| Outdoor HSV tuning for dry/shot targets | #21 | C | high | cv | open; YOLO primary in SITL/field config; HSV for shot fallback |
| Shot detection after real spray | #23 | C | high | cv | open; needs wet target + lighting on hardware |
| Train/export dry + shot ONNX models | #19 | C | medium | cv | **partial**; `best.onnx` dry integrated; shot ONNX missing |
| CV regression set from recorded footage | #22 | C | medium | cv | open |
| Depth sensor field validation (ArduCam + H-Flow) | #26 | D | high | metric-recon | **partial**; drivers + cal tools on `main`; needs hardware pass |
| FOV / depth calibration vs tape measure | #27 | D | medium | metric-recon | **partial**; `validate_calibration.py`; needs live captures |
| Auto-nav PD gain tuning (no oscillation) | #28 | D | high | auto-nav | **partial**; SITL gains tuned (`vion.yaml` sitl profile); field tune pending |
| Side clearance calibration with real scene | #29 | D | medium | auto-nav | open |
| Real Google Drive upload | #25 | D | high | upload | open; local copy only in dev/SITL |
| Multi-target flight window test (Phase 4) | #71 | E | high | field-test | **deprioritized**; daily driver is single-target; optional `-MaxTargets 2` |
| Target-loss recovery on real feed | #73 | E | medium | cv | **partial**; SITL hold/search remediation; field CV latency TBD |
| scrcpy latency field tuning | #72 | E | medium | infra | deprioritized; RPi primary path |
| Roadmap phases 0-6 | #78 | - | high | field-test | Phase 0-2 code/SITL ready; 3-6 need hardware |
| GitHub Projects board + recruit welcome | #8 | A | medium | infra | open; WELCOME/ONBOARDING/branches.md updated on `main` |
| Task 1 Vivi field test (Phase 5) | #77 | - | medium | task1 | open |
| Autonomous takeoff/landing (CONOPS 5+5 pts) | #75 | F | low | auto-nav | open; SITL has NAV_TAKEOFF preflight only |
| Adapt config when 2027 CONOPS publishes | #76 | F | low | infra | open |
| Vivi/Vulcan2 FC Lua + Mission Planner docs | #17 | B | low | infra | open |

See [field-test-plan.md](runbooks/field-test-plan.md) for phased pass criteria. SITL runbook: [sitl-overview.md](runbooks/sitl-overview.md).
