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

## Status

Task 1 code migration from old-codebase is Track B1 (not yet complete).
