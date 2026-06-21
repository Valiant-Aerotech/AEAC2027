# Autonomy module (Task 2)

Pipeline: **CV → Metric Recon (3D) → Auto-Nav (3D motion) → Spray → Upload**

Entry point: `hardware/vion/rpi/run_mission.py` (Pi) or `missions/task2_vion_auto_extinguish.py` (GCS) → `orchestrator.py`

## Layout

```
autonomy/
  orchestrator.py       # State machine, SITL/field modes, main loop
  packets.py            # CVPacket, MetricPacket (3D fields)
  auto_nav/             # Planner, visual servo, MAVLink driver
  cv/                   # Public API: detector, overlay, SITL dashboard
  metric_recon/         # edge_proximity, aim_offset, geometry_3d, depth, FOV, clearance
  spray/                # Aim check (pixel + altitude), water trigger
  upload/               # Task 2 photo naming + Drive
  safety/               # Battery, geofence, timeout
  flight/               # Profile merge (sitl, vivi, …)
  sitl_motion.py        # SITL: 3D NED motion stack (Backoff → Follow → Search → Hold)
  sitl_preflight.py     # SITL: arm / takeoff, ensure GUIDED
  sitl_pattern.py       # SITL: guided box pattern + LOITER (no CV)
  gcs_hud.py            # Mission Planner T2: STATUSTEXT
  sitl_search.py        # SITL: 3D search creep + approach speed
  cv/sitl_map_view.py   # SITL: 3-panel dashboard

common/
  ned_kinematics.py     # Rotation matrices, 3D velocity toward goal, VehiclePose
  sitl_physics.py       # Pose drain, target projection
```

## Run modes

| Mode | Flag / profile | Doc |
|------|----------------|-----|
| Field (Vion Pi) | `run_mission.py --profile indoor` (or `outdoor`) | `hardware/vion/rpi/README.md` |
| Vivi bench / hand-test | `run_mission.py --profile vivi --hand-test` | `docs/runbooks/vivi-hand-test.md` |
| SITL simulation | `--sitl` + `flight_profiles.sitl` | `docs/runbooks/sitl-overview.md` |
| Bench CV | `python tools/valiant.py bench cv` | `ONBOARDING.md` |
| Bench metric (3D) | `python tools/valiant.py bench metric` | `docs/interfaces.md` |
| CV training | `python -m valiant.autonomy.cv.training.train` | `models/README.md` |

Docs: [docs/branches.md](../../../docs/branches.md) (feature branches + PRs into `main`). Tools: [tools/README.md](../../../tools/README.md).
