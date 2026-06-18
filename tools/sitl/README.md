# SITL tools

Scripts for **software-in-the-loop** testing. No physical drone.

| Script | Run from | Purpose |
|--------|----------|---------|
| [`../launch_sitl.ps1`](../launch_sitl.ps1) | Windows repo root | Start ArduPilot SITL in WSL |
| [`launch_sitl.sh`](launch_sitl.sh) | WSL (called by above) | `sim_vehicle.py` wrapper |
| [`../run_sitl_mission.ps1`](../run_sitl_mission.ps1) | Windows repo root | Mission + optional telemetry monitor |
| [`../run_sitl_tests.ps1`](../run_sitl_tests.ps1) | Windows repo root | SITL unit + integration pytest |
| [`../download_sitl_map.py`](../download_sitl_map.py) | Windows | Satellite imagery for top-down panel |
| [`../mission_monitor.py`](../mission_monitor.py) | Windows | UDP state/velocity HUD |

**Docs:** [docs/runbooks/sitl-overview.md](../../docs/runbooks/sitl-overview.md) (start here) · [sitl-wsl.md](../../docs/runbooks/sitl-wsl.md) (WSL install)

**Quick start:**

```powershell
.\tools\launch_sitl.ps1          # terminal 1
.\tools\run_sitl_mission.ps1     # terminal 2
```
