# Deploy model and calibration to Pi (bringup Phase C3)
param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,

    [string]$PiPath = "~/AEAC2027",
    [switch]$SkipModel,
    [switch]$SkipCalibration
)
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "=== Deploy to Pi: $PiHost ===" -ForegroundColor Cyan

if (-not $SkipModel) {
    $model = Join-Path $RepoRoot "models\best.onnx"
    if (-not (Test-Path $model)) {
        Write-Host "ERROR: models\best.onnx not found on laptop" -ForegroundColor Red
        exit 1
    }
    Write-Host "Copying best.onnx..."
    scp $model "${PiHost}:${PiPath}/models/"
}

if (-not $SkipCalibration) {
    $cal = Join-Path $RepoRoot "config\vion_calibration.yaml"
    if (-not (Test-Path $cal)) {
        Copy-Item (Join-Path $RepoRoot "config\vion_calibration.yaml.example") $cal
        Write-Host "Created local vion_calibration.yaml from example"
    }
    Write-Host "Copying vion_calibration.yaml..."
    scp $cal "${PiHost}:${PiPath}/config/"
}

Write-Host "OK. On Pi run: python hardware/vion/rpi/check_sensors.py"
