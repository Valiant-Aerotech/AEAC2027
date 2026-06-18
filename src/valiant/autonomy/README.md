# Autonomy module (Task 2)

Pipeline: **CV → Metric Recon → Auto-Nav → Spray → Upload**

Entry point: `missions/task2_vion_auto_extinguish.py` → `orchestrator.py`

## Layout

```
autonomy/
  orchestrator.py       # State machine, SITL/field modes, main loop
  packets.py            # CVPacket, MetricPacket
  auto_nav/             # Planner, visual servo, MAVLink driver
  cv/                   # HSV, YOLO, detector, overlay UI, SITL dashboard
  cv-archive/           # Archived CV layout (reference)
  metric_recon/         # Distance / clearance from bbox + rangefinder
  spray/                # Aim check, water trigger
  upload/               # Task 2 photo naming + Drive
  safety/               # Battery, geofence, timeout
  flight/               # Profile merge (sitl, vivi, …)
  sitl_motion.py        # SITL-only: Stanley-style motion stack
  sitl_preflight.py     # SITL-only: arm / takeoff
  sitl_search.py        # SITL-only: search + altitude helpers
  cv/sitl_map_view.py   # SITL-only: 3-panel dashboard
```

## Run modes

| Mode | Flag / profile | Doc |
|------|----------------|-----|
| Field (Vion GCS) | default `vion` | `docs/runbooks/task2-vion-auto.md` |
| SITL simulation | `--sitl` + `flight_profiles.sitl` | `docs/runbooks/sitl-overview.md` |
| Vivi onboard | `flight_profiles.vivi` | `docs/runbooks/vivi-hand-test.md` |
| Bench CV only | `tools/cv_bench_test.py` | `ONBOARDING.md` |
| Standalone CV scripts | `src/valiant/cv/task2_cv_script.py` | training / convolute inference |

Docs: [docs/branches.md](../../../docs/branches.md) (develop on **`main`**).
