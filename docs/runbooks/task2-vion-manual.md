# Runbook - Task 2 Vion Manual Photo

Use when autonomous extinguishing fails or for operator-flown runs.

## Run

```powershell
python missions\task2_vion_manual_photo.py
python missions\task2_vion_manual_photo.py --source scrcpy
python missions\task2_vion_manual_photo.py --source scrcpy --upload
python missions\task2_vion_manual_photo.py --camera 0 --team ValiantAerotech
```

## Operator steps

1. Fly Vion manually to each target and extinguish with the water trigger
2. Point camera at extinguished target (blue paint visible)
3. Press **ENTER** in the capture window to save the photo
4. Repeat for each target
5. Press **Q** to quit

Photos save under `task2_photos/` with filenames `Task_2_{team}_target_{N}.jpg`. A CSV log is written to `task2_photo_log.csv`.

With `--upload`, each saved photo is also copied (or uploaded to Drive if configured).

## scrcpy source

`--source scrcpy` uses the same `ExtinguisherCam` window as the auto mission. Ensure the phone is connected and scrcpy launches before capturing.
