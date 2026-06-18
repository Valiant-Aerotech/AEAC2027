# GitHub Issues Backlog

Use `tools/create_github_issues.ps1` to create these on [Valiant-Aerotech/AEAC2027](https://github.com/Valiant-Aerotech/AEAC2027).

```powershell
gh auth login
.\tools\create_github_issues.ps1
```

## Labels

| Label | Use |
|-------|-----|
| `track-a` ... `track-f` | Which roadmap track |
| `done` | Implemented in repo - issue closed for history |
| `field-test` | Needs outdoor / flight validation |
| `refinement` | Works on bench, needs tuning |
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

## Issue summary

### Closed on create (done in repo)

Tracks A1-A7, B1-B8, C1-C7, C9, D1-D9 (code), E1, E5, E6, F1-F4, F6

### Open - refinement and field test (priority order)

Canonical GitHub issue numbers in parentheses. Duplicate issues (#47–#68) were closed 2026-06-11.

| Issue | GH | Track | Priority | Module | Repo status |
|-------|-----|-------|----------|--------|-------------|
| Outdoor HSV tuning for dry/shot targets | #21 | C | high | cv | open — YOLO primary; HSV for shot fallback |
| Train/export dry + shot ONNX models | #19 | C | medium | cv | **partial** — dry YOLO integrated; shot ONNX missing |
| Shot detection after real spray (blur, lighting) | #23 | C | high | cv | open |
| CV regression set from recorded field footage | #22 | C | medium | cv | open |
| Depth sensor field validation (ArduCam + H-Flow) | #26 | D | high | metric-recon | **partial** — code + cal tools; needs hardware pass |
| FOV / depth calibration vs tape measure | #27 | D | medium | metric-recon | **partial** — `validate_calibration.py` 10% gate; needs live captures |
| Auto-nav PD gain tuning (no oscillation) | #28 | D | high | auto-nav | **partial** — distance-scaled approach; field tune pending |
| Side clearance calibration with real scene | #29 | D | medium | auto-nav | open |
| Real Google Drive upload | #25 | D | high | upload | open — local copy only |
| Full pipeline field test - single target (Phase 3) | #70 | E | high | field-test | open — bringup scripts ready |
| Multi-target flight window test (Phase 4) | #71 | E | high | field-test | open |
| scrcpy latency field tuning | #72 | E | medium | infra | deprioritized — RPi primary path |
| GitHub Projects board + recruit welcome message | #8 | A | medium | infra | open |
| Task 1 Vivi field test (Phase 5) | #77 | - | medium | task1 | open |
| Autonomous takeoff/landing (CONOPS 5+5 pts) | #75 | F | low | auto-nav | open |
| Adapt config when 2027 CONOPS publishes | #76 | F | low | infra | open |
| Vivi/Vulcan2 FC Lua + Mission Planner docs | #17 | B | low | infra | open |
| AEAC2027 field test phases 0-6 (roadmap) | #78 | - | high | field-test | Phases 0–2 code ready; 3–6 need hardware |

See [field-test-plan.md](runbooks/field-test-plan.md) for phased pass criteria.
