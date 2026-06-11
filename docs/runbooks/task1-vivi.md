# Runbook - Task 1 Vivi Survey

## Prerequisites

- Vivi telemetry via Mission Planner (`udpin:127.0.0.1:14550`)
- Operator knows building corner capture order (A, B, C)

## Run

```powershell
python missions\task1_vivi_survey.py
python missions\task1_vivi_survey.py --team "Valiant Aerotech" --camera-offset-cm 10
```

## Output

`Task_1_<team>_targets.txt` - upload before flight window ends.

## CONOPS

Report filename follows `config/conops.yaml` (`Task_1_{team}_targets.txt`). See [docs/conops.md](../conops.md).
