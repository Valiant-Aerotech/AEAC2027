# SITL overview — virtual drone + motion

Software-in-the-loop (SITL) runs ArduPilot on your laptop so you can exercise
**GUIDED hold**, pattern, orbit, and mission dry-runs **without a physical aircraft**.

## What is simulated?

| Layer | Real hardware | SITL substitute |
|-------|---------------|-----------------|
| Flight controller | Pixhawk | ArduPilot SITL in WSL (`sim_vehicle.py`) |
| Radio | COM / SiK | TCP `127.0.0.1:5760` (legacy) or **5762** (MAVProxy path) |
| Companion motion | `valiant-mav` Vehicle / guided | Same Python against TCP |
| Scoring math | Survey / tagtrack | Offline `--dry-run` (no FC required) |

Perception worlds under `tests/fixtures/sitl_*.json` remain available for camera/geometry unit tests. Full CV-in-the-loop survey is not required for the motion gate.

## Preferred path (valiant-mav)

**Terminal 1** (WSL):

```bash
cd ~/ardupilot && ./Tools/autotest/sim_vehicle.py -v ArduCopter --console --map
```

Companion default: **tcp:127.0.0.1:5762**.

**Terminal 2** (Windows repo):

```powershell
python tools\valiant.py sitl pattern
python tools\valiant.py sitl orbit --laps 1
python tools\valiant.py survey --dry-run
python tools\valiant.py tagtrack --dry-run
```

## Legacy Windows wrapper (tcp:5760)

```powershell
.\tools\launch_sitl.ps1          # terminal 1
python tools\valiant.py sitl pattern   # terminal 2
```

Optional Mission Planner map: TCP `127.0.0.1:5762` when using MAVProxy. STATUSTEXT check: `python tools\valiant.py gcs verify-statustext`.

## Config overlays

| File | Role |
|------|------|
| `config/sitl_missions/orbit.yaml` | Field-orbit geometry for SITL |
| `config/sitl_missions/pattern_box.yaml` | Box pattern speeds / altitudes |

These are motion overlays, not fire-mission scenario YAMLs.

## Safety contract (same as field)

- Companion **never** terminates. Soft boundary → hold + STATUSTEXT.
- Software holds use **GUIDED hold**, not LOITER.
- Uncaught faults → `hold_after_fault`.

WSL install details: [sitl-wsl.md](sitl-wsl.md). Sibling docs: `../valiant-mav/docs/sitl.md`.
