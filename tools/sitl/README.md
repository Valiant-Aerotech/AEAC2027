# SITL tools

Scripts for **software-in-the-loop** testing. No physical drone.

| Script | Run from | Purpose |
|--------|----------|---------|
| [`../launch_sitl.ps1`](../launch_sitl.ps1) | Windows repo root | Start ArduPilot SITL in WSL |
| [`launch_sitl.sh`](launch_sitl.sh) | WSL (called by above) | `sim_vehicle.py` wrapper |
| [`../run_sitl_mission.ps1`](../run_sitl_mission.ps1) | Windows repo root | Mission + optional telemetry monitor |
| [`../run_sitl_tests.ps1`](../run_sitl_tests.ps1) | Windows repo root | SITL unit + integration pytest |

CLI equivalents: `python tools/valiant.py sitl mission`, `sitl test`, `sitl map download`, `gcs monitor`.

**Docs:** [docs/runbooks/sitl-overview.md](../../docs/runbooks/sitl-overview.md) · [sitl-wsl.md](../../docs/runbooks/sitl-wsl.md)

**Quick start:**

```powershell
.\tools\launch_sitl.ps1          # terminal 1
python tools\valiant.py sitl mission   # terminal 2
```
