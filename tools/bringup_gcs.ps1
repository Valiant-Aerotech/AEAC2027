# First connect to drone (GCS laptop + telemetry radio)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== Vion GCS first-connect bringup ===" -ForegroundColor Cyan
Write-Host ""

Write-Host "1. Mission Planner (manual):" -ForegroundColor Yellow
Write-Host "   - Connect telemetry radio COM @ 57600"
Write-Host "   - Confirm heartbeat + battery"
Write-Host "   - Run: .\tools\print_fc_params.ps1  (Pi TELEM + H-Flow params)"
Write-Host "   - Test SERVO15: python tools\test_spray_gcs.py"
Write-Host "   - Test emergency RC switch"
Write-Host ""

Write-Host "2. GCS software setup..." -ForegroundColor Yellow
& "$PSScriptRoot\setup_gcs.ps1"

Write-Host ""
Write-Host "3. Environment checks..." -ForegroundColor Yellow
python tools\verify_env.py
python tools\conops_check.py

Write-Host ""
Write-Host "4. MAVLink heartbeat (drone powered, radio connected)..." -ForegroundColor Yellow
python tools\check_mavlink_gcs.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: MAVLink check failed. Fix COM port in config\vion.yaml and retry." -ForegroundColor Yellow
}

Write-Host ""
$vionYaml = Join-Path $RepoRoot "config\vion.yaml"
if (Test-Path $vionYaml) {
    $match = Select-String -Path $vionYaml -Pattern 'connection:\s*"(COM\d+)"' | Select-Object -First 1
    if ($match) {
        $conn = $match.Matches.Groups[1].Value
        Write-Host "config\vion.yaml mavlink.connection = $conn" -ForegroundColor Green
    } else {
        Write-Host "Edit config\vion.yaml -> mavlink.connection to your radio COM port" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "5. Pi deploy (when Pi is online):" -ForegroundColor Yellow
Write-Host "   .\tools\deploy_to_pi.ps1 -PiHost <user>@<pi-ip>"
Write-Host "   .\tools\run_calibration_pipeline.ps1 -PiHost <user>@<pi-ip>"
Write-Host "   .\tools\run_monitor.ps1"
Write-Host ""
Write-Host "See docs\runbooks\vion-bringup.md"
