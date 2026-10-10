# Welcome to Valiant Aerotech Software

You are joining the AEAC2027 autonomy stack (Task 1 survey + Task 2 tag & track).

## Start here

**[START_HERE.md](START_HERE.md)** — step-by-step for someone who has never run the repo.

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
git checkout main
git pull origin main
git checkout -b feature/your-topic
pip install -e ..\valiant-mav
.\start.ps1
python tools\valiant.py guide
```

Then read [ONBOARDING.md](ONBOARDING.md) and [docs/conops-2027.md](docs/conops-2027.md).

## Three things people usually want

| Goal | Command |
|------|---------|
| **Try software (no drone)** | `python tools\valiant.py quickstart` then `survey --dry-run` |
| **Virtual motion (SITL)** | `sim_vehicle` / `launch_sitl.ps1` + `sitl pattern` or `sitl orbit` |
| **Connect real hardware** | `python tools\valiant.py bringup phase1` |

## Efficiency rules (short)

1. Mission code stays thin under `missions/`.
2. Reuse `valiant-mav` motion — do not fork a second GUIDED stack.
3. One STATUSTEXT channel (`say` / `notify_crew`).
4. Soft boundary → hold; never Python terminate.
5. `reference/` is study-only — do not revive fire/spray into `src/`.

## Next reading

- [docs/lessons-learned.md](docs/lessons-learned.md)
- [docs/runbooks/sitl-wsl.md](docs/runbooks/sitl-wsl.md)
- [docs/branches.md](docs/branches.md)
