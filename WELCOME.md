# Welcome to Valiant Aerotech Software

You are joining the AEAC2027 autonomy stack.

## Start here

**[START_HERE.md](START_HERE.md)** — step-by-step for someone who has never run the repo.

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
git checkout main
.\start.ps1
python tools\valiant.py guide
```

Then read [ONBOARDING.md](ONBOARDING.md) and [docs/architecture.md](docs/architecture.md).

## Three things people usually want

| Goal | Command |
|------|---------|
| **Try software (no drone)** | `python tools\valiant.py quickstart` then `bench cv --camera 0` |
| **Virtual full mission** | `launch_sitl.ps1` + `python tools\valiant.py sitl mission` |
| **Connect real hardware** | `python tools\valiant.py bringup phase1` |

## Pick your first GitHub issue

Open [GitHub Issues](https://github.com/Valiant-Aerotech/AEAC2027/issues):

| Label | Good for |
|-------|----------|
| `cv` | Computer vision, HSV tuning |
| `auto-nav` | MAVLink motion, approach tuning |
| `field-test` | Outdoor validation |
| `infra` | Docs, setup |

Recommended: [#21](https://github.com/Valiant-Aerotech/AEAC2027/issues/21) outdoor CV tuning, [#22](https://github.com/Valiant-Aerotech/AEAC2027/issues/22) regression footage.

## Pipeline (whiteboard)

```
CV -> Metric Recon -> Auto-Nav -> Spray -> Upload
```

Code: `src/valiant/autonomy/`. Tools: `python tools\valiant.py guide`.

## Rules

- Never commit secrets (`config/gdrive_credentials.json`)
- Config: `config/vion.yaml`, `config/conops.yaml`
- Ask before changing orchestrator state machine logic
