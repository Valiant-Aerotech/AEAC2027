# Welcome to Valiant Aerotech Software

You are joining the AEAC2027 autonomy stack. This repo runs on a **fresh GCS laptop** with minimal setup.

## First hour

```powershell
git clone https://github.com/Valiant-Aerotech/AEAC2027.git
cd AEAC2027
git checkout main
.\tools\setup.ps1
python tools\verify_env.py
python tools\conops_check.py
```

Read [ONBOARDING.md](ONBOARDING.md) then [docs/architecture.md](docs/architecture.md). All development is on **`main`**; see [docs/branches.md](docs/branches.md).

## Pick your first task

Open [GitHub Issues](https://github.com/Valiant-Aerotech/AEAC2027/issues) and filter by label:

| Label | Good for |
|-------|----------|
| `cv` | Computer vision, HSV tuning, training data |
| `auto-nav` | MAVLink motion, approach tuning |
| `metric-recon` | Distance estimation, rangefinder |
| `field-test` | Outdoor validation (needs flight line access) |
| `infra` | Docs, setup, GitHub board |

**Recommended first issues for new members:**

1. [#60 C10](https://github.com/Valiant-Aerotech/AEAC2027/issues/60) - Outdoor HSV tuning (print purple circles, run `cv_bench_test.py`)
2. [#61 C11](https://github.com/Valiant-Aerotech/AEAC2027/issues/61) - Record footage, run `cv_regression_test.py`
3. [#47 A8](https://github.com/Valiant-Aerotech/AEAC2027/issues/47) - Help maintain GitHub Projects board

## Module map (whiteboard)

```
CV -> Metric Recon -> Auto-Nav -> Spray -> Upload
```

Code lives in `src/valiant/autonomy/`. You only run scripts in `missions/` and `tools/`.

## Rules

- Never commit `config/gdrive_credentials.json` or secrets
- Config changes go in `config/vion.yaml` or `config/conops.yaml`
- Ask in team chat before changing orchestrator state machine logic

## Get unblocked

- COM port issues: edit `config/vion.yaml`
- CV not detecting: tune `cv.hsv_dry` / `cv.hsv_shot`
- Full checklist: [docs/runbooks/field-test-plan.md](docs/runbooks/field-test-plan.md)
