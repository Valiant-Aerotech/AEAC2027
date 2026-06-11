# GitHub Issues Backlog

Use `tools/create_github_issues.ps1` to create these on [valiant-aerotech/AEAC2027](https://github.com/valiant-aerotech/AEAC2027).

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

| Issue | Track | Priority | Module |
|-------|-------|----------|--------|
| Outdoor HSV tuning for dry/shot targets | C | high | cv |
| Train/export dry + shot ONNX models | C | medium | cv |
| Shot detection after real spray (blur, lighting) | C | high | cv |
| CV regression set from recorded field footage | C | medium | cv |
| VL53L1X rangefinder field validation | D | high | metric-recon |
| FOV distance calibration vs tape measure | D | medium | metric-recon |
| Auto-nav PD gain tuning (no oscillation) | D | high | auto-nav |
| Side clearance calibration with real scene | D | medium | auto-nav |
| Real Google Drive upload | D | high | upload |
| Full pipeline field test - single target (Phase 3) | E | high | field-test |
| Multi-target flight window test (Phase 4) | E | high | field-test |
| scrcpy latency field tuning | E | medium | infra |
| GitHub Projects board + recruit welcome message | A | medium | infra |
| Task 1 Vivi field test (Phase 5) | - | medium | task1 |
| Autonomous takeoff/landing (CONOPS 5+5 pts) | F | low | auto-nav |
| Adapt config when 2027 CONOPS publishes | F | low | infra |
| Vivi/Vulcan2 FC Lua + Mission Planner docs | B | low | infra |

See [field-test-plan.md](runbooks/field-test-plan.md) for phased pass criteria.
