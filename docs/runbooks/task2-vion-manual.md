# Runbook - Task 2 Vion Manual Photo

## When to use

Autonomy is unstable or competition-day fallback. Operator flies Vion manually and extinguishes targets by hand.

## Run

```powershell
python missions\task2_vion_manual_photo.py
python missions\task2_vion_manual_photo.py --team ValiantAerotech --camera 0
```

## Operator steps

1. Fly to target manually
2. Shoot water manually
3. Press ENTER in camera window to save photo
4. Repeat for next target
5. Press Q to quit

Photos saved to `task2_photos/Task_2_<team>_target_N.jpg`.
