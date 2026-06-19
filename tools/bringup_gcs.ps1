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
Write-Host "   - Test SERVO15: python tools\valiant.py gcs spray"
Write-Host "   - Test emergency RC switch"
Write-Host ""

Write-Host "2. GCS software setup..." -ForegroundColor Yellow
& "$PSScriptRoot\setup.ps1"
if (-not (Test-Path "config\vion_calibration.yaml")) {
    Copy-Item "config\vion_calibration.yaml.example" "config\vion_calibration.yaml"
    Write-Host "Created config\vion_calibration.yaml from example"
}

Write-Host ""
Write-Host "3. Environment checks..." -ForegroundColor Yellow
python tools\valiant.py env check
python tools\valiant.py conops check

Write-Host ""
Write-Host "4. MAVLink heartbeat (drone powered, radio connected)..." -ForegroundColor Yellow
python tools\valiant.py gcs heartbeat
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
Write-Host "   python tools\valiant.py gcs monitor"
Write-Host ""
Write-Host "See docs\runbooks\vion-bringup.md"
