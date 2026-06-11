# Create AEAC2027 backlog issues on GitHub
# Prerequisite: gh auth login
# Usage: .\tools\create_github_issues.ps1
#        .\tools\create_github_issues.ps1 -DryRun

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$Repo = "valiant-aerotech/AEAC2027"

function Ensure-Gh {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        Write-Error "gh CLI not found. Install: winget install GitHub.cli"
    }
    if ($DryRun) { return }
    gh auth status 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Not logged in. Run: gh auth login"
    }
}

function Ensure-Label($Name, $Color, $Description) {
    if ($DryRun) { return }
    $labels = gh label list --repo $Repo --json name 2>$null | ConvertFrom-Json
    $exists = $labels | Where-Object { $_.name -eq $Name }
    if (-not $exists) {
        gh label create $Name --repo $Repo --color $Color --description $Description 2>$null
    }
}

function Ensure-Milestone($Title, $Description) {
    if ($DryRun) { return $Title }
    $milestones = gh api "repos/$Repo/milestones" 2>$null | ConvertFrom-Json
    $exists = $milestones | Where-Object { $_.title -eq $Title }
    if ($exists) { return $Title }
    $body = @{ title = $Title; description = $Description; state = "open" } | ConvertTo-Json -Compress
    $tmp = New-TemporaryFile
    Set-Content -Path $tmp -Value $body -Encoding utf8
    gh api "repos/$Repo/milestones" -X POST --input $tmp | Out-Null
    Remove-Item $tmp
    return $Title
}

function Find-OpenIssue($Title) {
    $issues = gh issue list --repo $Repo --state all --limit 200 --json title,number,state 2>$null | ConvertFrom-Json
    return $issues | Where-Object { $_.title -eq $Title } | Select-Object -First 1
}

function New-Issue($Title, $Body, $Labels, $Milestone, [switch]$Close) {
    $existing = Find-OpenIssue $Title
    if ($existing) {
        Write-Host "[skip] $Title (already #$($existing.number))"
        return
    }
    $labelStr = $Labels -join ","
    Write-Host "$(if ($Close) {'[close]'} else {'[open] '}) $Title"
    if ($DryRun) { return }
    $bodyFile = New-TemporaryFile
    Set-Content -Path $bodyFile -Value $Body -Encoding utf8
    $issueUrl = gh issue create --repo $Repo --title $Title --body-file $bodyFile --label $labelStr --milestone $Milestone
    Remove-Item $bodyFile
    if ($Close -and $issueUrl) {
        $num = ($issueUrl -split "/")[-1]
        gh issue close $num --repo $Repo --comment "Implemented in AEAC2027 repo. Closed by create_github_issues.ps1"
    }
}

Ensure-Gh

$labels = @(
    @("track-a", "0E8A16", "Track A - Foundation"),
    @("track-b", "1D76DB", "Track B - Migration"),
    @("track-c", "5319E7", "Track C - CV module"),
    @("track-d", "B60205", "Track D - Metric Recon + Auto-Nav + Spray"),
    @("track-e", "FBCA04", "Track E - Hardening"),
    @("track-f", "006B75", "Track F - CONOPS"),
    @("done", "C5DEF5", "Implemented in repo"),
    @("field-test", "E99695", "Needs flight or outdoor validation"),
    @("refinement", "FEF2C0", "Bench works, needs tuning"),
    @("cv", "D4C5F9", "Computer vision"),
    @("metric-recon", "BFDADC", "Metric reconstruction"),
    @("auto-nav", "C2E0C6", "Auto navigation"),
    @("spray", "F9D0C4", "Spray / actuation"),
    @("upload", "EDEDED", "Upload / Drive"),
    @("task1", "1D76DB", "Vivi Task 1"),
    @("infra", "CCCCCC", "Repo / team infra"),
    @("priority-high", "B60205", "Blocks competition readiness"),
    @("priority-medium", "FBCA04", "Important but not blocking"),
    @("priority-low", "0E8A16", "Nice to have")
)
foreach ($l in $labels) { Ensure-Label $l[0] $l[1] $l[2] }

$msA = Ensure-Milestone "Track A - Foundation" "Scaffold, docs, onboarding"
$msB = Ensure-Milestone "Track B - Migration" "Migrate old-codebase baseline"
$msC = Ensure-Milestone "Track C - CV Module" "Dry/shot detection, CVPacket, training"
$msD = Ensure-Milestone "Track D - Pipeline" "Metric recon, auto-nav, spray, upload"
$msE = Ensure-Milestone "Track E - Hardening" "Field tests, safety, scrcpy"
$msF = Ensure-Milestone "Track F - CONOPS" "Competition rules adaptation"
$msFT = Ensure-Milestone "Field Test" "Phased validation per field-test-plan.md"

# --- Track A (done) ---
New-Issue "A1: Scaffold repo layout" "Folders, pyproject.toml, missions/, src/valiant/, config/, hardware/, tools/, docs/`n`nDone in AEAC2027." @("track-a","done","infra") $msA -Close
New-Issue "A2: setup.ps1 + verify_env.py" "One-command laptop bootstrap.`n`nDone." @("track-a","done","infra") $msA -Close
New-Issue "A3: README + ONBOARDING" "New member quick start.`n`nDone." @("track-a","done","infra") $msA -Close
New-Issue "A4: docs/drones.md fleet reference" "Vulcan 2, Vion, Vivi roles.`n`nDone." @("track-a","done","infra") $msA -Close
New-Issue "A5: docs/architecture.md whiteboard modules" "CV -> Metric Recon -> Auto-Nav pipeline doc.`n`nDone." @("track-a","done","infra") $msA -Close
New-Issue "A6: docs/interfaces.md packet specs" "CVPacket, MetricPacket contracts.`n`nDone." @("track-a","done","infra") $msA -Close
New-Issue "A7: config templates vion/vivi/vulcan2" "Per-drone YAML with comments.`n`nDone." @("track-a","done","infra") $msA -Close
New-Issue "A8: GitHub Projects board + recruit welcome message" "## Goal`nSet up GitHub Projects v2 board for AEAC2027 and post welcome message for new recruits (Jacob, Matt, others).`n`n## Tasks`n- [ ] Create project board with columns: Backlog, Ready, In Progress, Field Test, Done`n- [ ] Link to docs/github-issues-backlog.md and field-test-plan.md`n- [ ] Draft welcome message: clone repo, run setup.ps1, read ONBOARDING.md, pick an issue`n- [ ] Assign module owners (CV, nav, integration)`n`n## Done when`nNew recruit can find an issue and run manual photo mission in under 30 minutes." @("track-a","infra","priority-medium") $msA

# --- Track B (done) ---
New-Issue "B1: Migrate Vivi Task 1" "task1/ package + task1_vivi_survey.py mission.`n`nDone." @("track-b","done","task1") $msB -Close
New-Issue "B2: Migrate visual_servo.py" "auto_nav/visual_servo.py PD controller.`n`nDone." @("track-b","done","auto-nav") $msB -Close
New-Issue "B3: Migrate water_trigger" "spray/actuation.py SERVO15.`n`nDone." @("track-b","done","spray") $msB -Close
New-Issue "B4: Migrate YOLO detector baseline" "cv/detector.py baseline.`n`nDone." @("track-b","done","cv") $msB -Close
New-Issue "B5: Migrate orchestrator baseline" "State machine + --sim.`n`nDone." @("track-b","done","auto-nav") $msB -Close
New-Issue "B6: Migrate manual_capture" "manual photo fallback mission.`n`nDone." @("track-b","done","upload") $msB -Close
New-Issue "B7: Vion hardware Lua + MP docs" "hardware/vion/ migrated.`n`nDone for Vion." @("track-b","done","infra") $msB -Close
New-Issue "B8: mavproxy_listen.py debug tool" "MAVLink STATUSTEXT listener.`n`nDone." @("track-b","done","infra") $msB -Close
New-Issue "B9: Vivi/Vulcan2 FC Lua + Mission Planner docs" "## Goal`nMigrate remaining FC scripts from old-codebase into hardware/vivi/ and hardware/vulcan2/.`n`n## Done when`nEach drone folder has lua/ and mission-planner/ with README explaining what goes on which FC." @("track-b","infra","priority-low") $msB

# --- Track C ---
New-Issue "C1-C7: CV module baseline" "CVPacket, HSV dry/shot, detector refactor, exceptions, ui overlay, generate_targets.py.`n`nDone. See src/valiant/autonomy/cv/" @("track-c","done","cv") $msC -Close
New-Issue "C8: Train and export dry + shot ONNX models" "## Goal`nProduce models/dry.onnx and models/shot.onnx for cv.method yolo/both.`n`n## Steps`n1. Collect or generate training images (outdoor purple circles, wetted blue)`n2. Label with ultralytics`n3. Run cv/training/train.py`n4. Bench test with cv_bench_test.py`n`n## Done when`nyolo mode detects dry targets on field footage with fewer false positives than HSV-only." @("track-c","cv","refinement","priority-medium") $msC
New-Issue "C9: CV bench test tooling" "tools/cv_bench_test.py logs CVPacket stream.`n`nDone." @("track-c","done","cv") $msC -Close
New-Issue "C10: Outdoor HSV tuning - dry and shot targets" "## Problem`nHSV thresholds in config/vion.yaml are tuned for synthetic images. Outdoor sun/shadow will cause missed detections and false positives.`n`n## Tasks`n- [ ] Print 5-30 cm purple competition circles`n- [ ] Run cv_bench_test at field site AM/PM lighting`n- [ ] Tune hsv_dry, hsv_shot, hsv_min_area_px`n- [ ] Document final values in runbook`n`n## Done when`n10 consecutive stable dry detections outdoors; shot detected within 3 s after wetting." @("track-c","cv","refinement","field-test","priority-high") $msC
New-Issue "C11: CV regression set from recorded footage" "## Goal`nRecord scrcpy footage at field tests; replay through cv_bench_test --video for regression.`n`n## Done when`nAt least 3 clips saved in team Drive; script logs false positive/negative counts per clip." @("track-c","cv","refinement","priority-medium") $msC
New-Issue "C12: Shot confirmation reliability after real spray" "## Problem`nVERIFYING state waits for CVPacket.shot. Motion blur, glare, and partial wetting may fail confirmation.`n`n## Tasks`n- [ ] Test with real spray at 0.8-1.5 m`n- [ ] Tune hsv_shot or add short post-spray settle delay in orchestrator`n- [ ] Log confirmation latency`n`n## Done when`nPhase 3 field test 3.2 passes 3/3 attempts." @("track-c","cv","field-test","priority-high") $msC

# --- Track D ---
New-Issue "D1-D9: Metric Recon + Auto-Nav + Spray code" "pixel_geometry, rangefinder, wall_distance, planner, mavlink_driver, aim.py, orchestrator wiring.`n`nDone." @("track-d","done","metric-recon","auto-nav","spray") $msD -Close
New-Issue "D10: Real Google Drive upload" "## Goal`nReplace local-copy default with gdrive_service_account upload.`n`n## Tasks`n- [ ] Service account JSON in config/gdrive_credentials.json (gitignored)`n- [ ] Set upload.folder_id in defaults.yaml`n- [ ] pip install google-api-python-client google-auth`n- [ ] Test upload from manual_capture --upload`n`n## Done when`nPhoto appears in team Drive within 15 s." @("track-d","upload","priority-high") $msD
New-Issue "D11: VL53L1X rangefinder field validation" "## Goal`nValidate MAVLink DISTANCE_SENSOR on Vion FC.`n`n## Tasks`n- [ ] Set metric_recon.rangefinder: vl53l1x`n- [ ] Run metric_bench_test with live link`n- [ ] Compare to tape measure at 1, 2, 3 m`n`n## Done when`nDistance within 15% of truth and planner 2 m gate works with rangefinder not FOV-only." @("track-d","metric-recon","field-test","priority-high") $msD
New-Issue "D12: FOV distance calibration" "## Goal`nFOV estimate uses target_diameter_m. Real targets are 5-30 cm.`n`n## Tasks`n- [ ] Test at known distances with known target size`n- [ ] Tune hfov_deg or target_diameter_m`n`n## Done when`nFOV distance within 25% at 2-4 m when rangefinder unavailable." @("track-d","metric-recon","refinement","field-test","priority-medium") $msD
New-Issue "D13: Auto-nav PD gain field tuning" "## Problem`nBench PD gains may oscillate or creep on real Vion.`n`n## Tasks`n- [ ] Phase 2 tests 2.2-2.3`n- [ ] Tune kp_x/y, deadband_px, approach_speed in vion.yaml`n`n## Done when`nTarget holds centre within deadband for 5 s without pilot override." @("track-d","auto-nav","field-test","refinement","priority-high") $msD
New-Issue "D14: Side clearance calibration" "Validate planner ABORT against real door frames and wall edges in scene.`n`nSee field-test-plan Phase 2.4." @("track-d","auto-nav","field-test","priority-medium") $msD

# --- Track E ---
New-Issue "E1-E2,E5-E6: Hardening baseline" "Safety monitor, scrcpy config, upload retries, runbooks, competition-day + field-test-plan docs.`n`nDone." @("track-e","done","infra") $msE -Close
New-Issue "E3: Full pipeline field test - single target (Phase 3)" "## Checklist`nSee docs/runbooks/field-test-plan.md Phase 3.`n`n## Pass`nOne full CONOPS cycle: detect, 2m approach, aim, fire, VERIFYING, photo, upload." @("track-e","field-test","priority-high") $msFT
New-Issue "E4: Multi-target flight window test (Phase 4)" "Two+ targets in one session with correct photo numbering and refill between.`n`nSee field-test-plan Phase 4." @("track-e","field-test","priority-high") $msFT
New-Issue "E5: scrcpy latency field tuning" "Tune camera.max_fps, max_size, video_bit_rate_mbps on real phone link.`n`nSee field-test-plan Phase 1.5." @("track-e","infra","refinement","priority-medium") $msE
New-Issue "E6: Target-loss recovery on real feed" "Occlusion and motion blur cause target loss. Tune max_frames_without_target.`n`nSee field-test-plan Phase 2.5." @("track-e","cv","refinement","priority-medium") $msE

# --- Track F ---
New-Issue "F1-F6: CONOPS 2026 baseline" "config/conops.yaml, multi-target loop, VERIFYING, photo naming, docs/conops.md.`n`nDone for 2026 rules." @("track-f","done","infra") $msF -Close
New-Issue "F7: Autonomous takeoff and landing (CONOPS 5+5 pts)" "## Goal`nOptional scoring: autonomous takeoff from flight line and landing return.`n`n## Note`nNot in orchestrator today. May be Mission Planner mission or new states.`n`n## Priority`nLow - manual TO/LD acceptable if autonomy extinguishing is solid." @("track-f","auto-nav","priority-low") $msF
New-Issue "F8: Adapt config when 2027 CONOPS publishes" "Update config/conops.yaml and docs/conops.md per new rules.`n`nTrigger: AEAC publishes 2027 CONOPS PDF." @("track-f","infra","priority-low") $msF

# --- Task 1 ---
New-Issue "T1: Task 1 Vivi field test (Phase 5)" "Building survey + target report at field site.`n`nSee field-test-plan Phase 5.`n`nOutput: Task_1_{team}_targets.txt on Drive." @("task1","field-test","priority-medium") $msFT

# --- Epic ---
New-Issue "Roadmap: AEAC2027 field test phases 0-6" "## Master checklist`n`ndocs/runbooks/field-test-plan.md`n`ndocs/runbooks/competition-day.md`n`ndocs/github-issues-backlog.md`n`n## Whiteboard gaps (need refinement)`n- CV: outdoor HSV, ONNX models, shot confirmation`n- Metric Recon: VL53L1X + FOV calibration`n- Auto-Nav: PD tuning, side clearance`n- Spray: actuation works; physical nozzle aim TBD if gimbal added`n- Upload: real Google Drive`n`nClose sub-issues as each phase passes." @("field-test","priority-high") $msFT

Write-Host "`nDone. View issues: https://github.com/$Repo/issues"
