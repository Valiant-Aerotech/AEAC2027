# First connect to drone (GCS laptop + telemetry radio)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\lib\script_paths.ps1")
$ctx = Initialize-ValiantScript -ScriptRoot $PSScriptRoot
$RepoRoot = $ctx.RepoRoot
$ToolsDir = $ctx.ToolsDir

Write-Host "=== RPAS GCS first-connect bringup ===" -ForegroundColor Cyan
Write-Host "New laptop? Run .\start.ps1 first. Scenario menu: python tools\valiant.py guide"
Write-Host ""

Write-Host "1. Mission Planner (manual):" -ForegroundColor Yellow
Write-Host "   - Connect telemetry radio COM @ 57600"
Write-Host "   - Confirm heartbeat + battery"
Write-Host "   - Run: .\tools\bringup\print_fc_params.ps1  (Pi TELEM + H-Flow params)"
Write-Host "   - Test SERVO15: python tools\valiant.py gcs spray"
Write-Host "   - Test emergency RC switch"
Write-Host ""

Write-Host "2. GCS software setup..." -ForegroundColor Yellow
& (Join-Path $ToolsDir "setup.ps1")
if ($LASTEXITCODE -ne 0) {
    Show-ValiantFailure "setup.ps1 failed" -Hints @("See errors above", "Run: .\tools\setup.ps1")
}
if (-not (Test-Path "config\rpas_calibration.yaml")) {
    Copy-Item "config\rpas_calibration.yaml.example" "config\rpas_calibration.yaml"
    Write-Host "Created config\rpas_calibration.yaml from example"
}

Write-Host ""
Write-Host "3. Environment checks..." -ForegroundColor Yellow
python tools\valiant.py env check
python tools\valiant.py conops check

Write-Host ""
Write-Host "4. MAVLink heartbeat (drone powered, radio connected)..." -ForegroundColor Yellow
python tools\valiant.py gcs heartbeat
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: MAVLink check failed. Fix COM port in config\rpas.yaml and retry." -ForegroundColor Yellow
}

Write-Host ""
$cfgFiles = @(
    (Join-Path $RepoRoot "config\rpas.yaml"),
    (Join-Path $RepoRoot "config\vion.yaml")
)
$conn = $null
foreach ($cfgFile in $cfgFiles) {
    if (-not (Test-Path $cfgFile)) { continue }
    $match = Select-String -Path $cfgFile -Pattern 'connection:\s*"(COM\d+)"' | Select-Object -First 1
    if ($match) {
        $conn = $match.Matches.Groups[1].Value
        break
    }
}
if ($conn) {
    Write-Host "mavlink.connection = $conn (config\rpas.yaml)" -ForegroundColor Green
} else {
    Write-Host "Edit config\rpas.yaml / config\vion.yaml -> mavlink.connection to your radio COM port" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "5. Pi deploy (when Pi is online):" -ForegroundColor Yellow
Write-Host "   .\tools\deploy\deploy_to_pi.ps1 -PiHost <user>@<pi-ip>"
Write-Host "   .\tools\calibrate\run_calibration_pipeline.ps1 -PiHost <user>@<pi-ip>"
Write-Host "   python tools\valiant.py gcs monitor"
Write-Host ""
Write-Host "See docs\runbooks\vion-bringup.md"
