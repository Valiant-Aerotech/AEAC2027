# CONOPS Adaptation (Track F)

Competition rules live in `config/conops.yaml`. When AEAC publishes a new CONOPS, update that file and the runbooks - the modular pipeline (CV, Metric Recon, Auto-Nav) should not need rewrites.

**Current baseline:** 2026 AEAC CONOPS (2027 rules not released yet).

Official document: [AEAC Annual Student Competition](https://www.aerialevolution.ca/annual-student-competition/)

## Requirement traceability

### Task 2 - Fire Extinguishing

| CONOPS requirement | Config / code | Status |
|--------------------|---------------|--------|
| Approach from >2 m parallel to target plane | `conops.task2.min_approach_distance_m` -> `metric_recon`, `MotionPlanner` | Implemented |
| Autonomous aiming / target lock | `auto_nav.deadband_px`, `spray/aim.py`, AIMING state | Implemented |
| Successful extinguishing (water on target) | `spray.duration_s`, SERVO actuation | Implemented |
| Real-time photo of extinguished target | VERIFYING state + shot CV detection, CAPTURING | Implemented |
| Upload photo to team Google Drive | `upload/` module, CONOPS filename | Implemented (local fallback default) |
| Photo naming `Task_2_{team}_target_{n}` | `conops.task2.photo_filename_template`, `conops.py` | Implemented |
| Target order numbering | Orchestrator `target_number` increments per extinguish | Implemented |
| Unknown target count | Multi-target loop SEARCHING after each upload | Implemented |
| Target diameter 5-30 cm | `target_diameter_min_m` / `target_diameter_max_m` | Config only (FOV uses max) |
| No partial autonomy points | Documented in `conops.task2.autonomy.all_or_nothing` | Documented |
| Autonomous takeoff (5 pts) | Not in orchestrator | Manual / future |
| Autonomous landing (5 pts) | Not in orchestrator | Manual / future |

### Task 1 - Fire Reconnaissance

| CONOPS requirement | Config / code | Status |
|--------------------|---------------|--------|
| Report file `Task_1_{team}_targets.txt` | `conops.task1.report_filename_template`, `task1/report.py` | Implemented |
| Allowed target colours | `conops.task1.allowed_colours`, `config/vivi.yaml` | Implemented |

## What to change when 2027 CONOPS drops

1. Download new CONOPS PDF from AEAC site
2. Update `config/conops.yaml` (colours, distances, filenames, scoring notes)
3. Run `python tools/conops_check.py` - fix any validation warnings
4. Update this doc and `docs/runbooks/competition-day.md`
5. Only touch module code if rules change detection geometry or mission flow (e.g. new target shapes)

## Multi-target mission flow

```
SEARCHING -> APPROACHING -> AIMING -> FIRING -> VERIFYING -> CAPTURING -> UPLOADING -> SEARCHING (next target)
```

Press Ctrl+C or hit `safety` abort to stop. Use `--max-targets 1` for single-target test runs.
