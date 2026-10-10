# SITL tools

Scripts for **software-in-the-loop** testing. No physical drone.

| Script | Purpose |
|--------|---------|
| [`../launch_sitl.ps1`](../launch_sitl.ps1) | Start ArduPilot SITL in WSL (tcp:5760, no MAVProxy) |
| [`launch_sitl.sh`](launch_sitl.sh) | WSL wrapper called by the PS1 |
| [`sitl_pattern_flight.py`](sitl_pattern_flight.py) | GUIDED box pattern → hold |
| [`sitl_orbit_flight.py`](sitl_orbit_flight.py) | GUIDED orbit → hold |
| [`../run_sitl_pattern.ps1`](../run_sitl_pattern.ps1) / [`../run_sitl_orbit.ps1`](../run_sitl_orbit.ps1) | Windows wrappers |

CLI: `python tools/valiant.py sitl pattern|orbit|test|setup-wsl|map download`.

**Preferred (valiant-mav):** in WSL run
`sim_vehicle.py -v ArduCopter --console --map` and connect the companion to **tcp:5762**.

**Docs:** [sitl-overview.md](../../docs/runbooks/sitl-overview.md) · [sitl-wsl.md](../../docs/runbooks/sitl-wsl.md) · sibling `../valiant-mav/docs/sitl.md`

```powershell
# Terminal 1: launch_sitl.ps1  OR  sim_vehicle --console --map
# Terminal 2:
python tools\valiant.py sitl pattern
python tools\valiant.py sitl orbit --laps 1
python tools\valiant.py survey --dry-run   # scoring path without FC
```

Overlays: `config/sitl_missions/orbit.yaml`, `pattern_box.yaml`.
