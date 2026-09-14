# Reference: 2026 fire-suppression code

Need lua / safety / SITL? Start at [`topics.md`](topics.md).

This folder is **inert**. It is not a Python package, it is not on `PYTHONPATH`, and
`pyproject.toml` excludes it from ruff, pytest and the build. Nothing here can be
imported by live code, and deleting the whole folder is a safe one-line operation.

It exists for one reason: the 2026 AEAC mission (indoor fire suppression) produced
some genuinely good engineering that is worth reading before solving a similar
problem for 2027. The full 2026 tree is preserved at git tag `aeac2026-final`; this
is the curated subset.

These files will not run as-is. They import modules that no longer exist
(`valiant.autonomy.packets`, `valiant.common.*`, `valiant.autonomy.conops`). That is
intentional — they are documents, not code. Two `__init__.py` files were renamed to
`__init___was.py` so Python cannot accidentally treat these directories as packages.

## What to look at, and why

### `orchestrator.py` — mission state machine
1,238 lines running `SEARCHING → APPROACHING → AIMING → FIRING → VERIFYING →
PHOTOGRAPHING → UPLOADING → COMPLETE`. The most useful reference in the repo for
structuring a long autonomous mission.

Worth studying: how every state has an explicit abort path; how pilot override is
checked on every tick rather than at state boundaries; how the safety monitor is
consulted independently of mission logic; how SITL and hardware share one code path
through flags rather than through subclassing. The 2027 mission runners
(`missions/survey/runner.py`, `missions/tagtrack/runner.py`) should follow this shape
but must add clean in-window restart, which this did not have — CONOPS 4.6 lets
bidders restart a task as many times as they like inside the flight window.

### `spray/` — payload actuation
`actuation.py` drives a payload either through a MAVLink servo channel or a Raspberry
Pi GPIO pin behind one interface, with the hardware choice in config. Directly
relevant to the 2027 tracker release mechanism and the biological sample gripper.
`aim.py` is the dual-gate pattern: do not actuate unless *both* the pixel alignment
and the altitude alignment are within tolerance. That two-condition gate is a good
habit for any irreversible action — releasing a tracker is exactly as one-shot as
firing water.

### `cv_fire/` — detection ensemble and overlay rendering
`detector.py` composes two independent backends (a YOLO ONNX model and an HSV colour
threshold) and merges their output into one packet. `hsv.py` shows the colour-threshold
approach that gave a cheap, fast, explainable fallback when the model was uncertain.
For 2027 the equivalent is deer silhouette detection plus the brightly-coloured leg
bands that identify the Task 2 target animal, and the blue 32-inch delivery pad —
all three are strong colour cues, so this pattern transfers almost directly.

`ui.py` is the mission overlay: bounding boxes, state text, metric hints drawn onto
the frame. Reusable presentation code, mission-specific labels.

`training/` — `train.py` is a thin YOLO training CLI, `generate_targets.py` synthesises
training images, and `Model_Training_pipeline.ipynb` is the full experimentation
notebook that produced the 2026 weights. Start here when training the deer and ear-tag
models rather than from scratch.

### `clearance/` — obstacle geometry from depth
Built for holding standoff from a wall and clearance from a ceiling while flying
indoors. `lateral_clearance.py` and `vertical_clearance.py` sample a depth map to
decide whether it is safe to keep moving; `wall_distance.py` enriches a metric packet
with wall range; `pixel_geometry.py` estimates distance from a known target size and
camera FOV band.

`edge_proximity.py` and `aim_offset.py` solve a subtler problem worth remembering: when
a target sits near the edge of the frame, the visual servo wants to centre it, but
centring it would fly the aircraft into the corner. The fix was to servo toward a
*virtual* aim point offset from the real target. Any low-altitude work near the ground
for 2027 sample pickup will hit the same class of problem.

### `task1_building_survey/` — 2026 Task 1, a different mission
Fourteen files surveying coloured targets on the walls of a building: ENU local frame,
wall planes, door references, corner capture, and projection of a pixel detection onto
a known wall plane.

The 2027 herd survey is unrelated in purpose but identical in mathematics — take a
detection in image space plus a vehicle pose and produce a world coordinate.
`localization.py` and `geometry.py` are the two files to read before writing
`perception/geometry.py`'s pixel-to-ground projection. The difference is that 2027
projects onto the ground plane rather than a vertical wall, which is the simpler case.

`report.py` is also worth a look: it both writes and re-parses its own output file,
which made the submission format testable. `missions/survey/report.py` should do the
same for the 2027 `.txt` submission.
