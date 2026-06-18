param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,
    [string]$RemoteDir = "~/AEAC2027"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Deploying repo to $PiHost:$RemoteDir ..."
ssh $PiHost "mkdir -p $RemoteDir"
scp -r src config hardware missions pyproject.toml README.md "${PiHost}:${RemoteDir}/"

if (Test-Path "models\best.onnx") {
    ssh $PiHost "mkdir -p $RemoteDir/models"
    scp models\best.onnx "${PiHost}:${RemoteDir}/models/"
    Write-Host "Deployed models/best.onnx"
} else {
    Write-Host "WARN: models\best.onnx not found locally"
}

if (Test-Path "config\vion_calibration.yaml") {
    scp config\vion_calibration.yaml "${PiHost}:${RemoteDir}/config/"
}

Write-Host "Done. On Pi: cd $RemoteDir && pip install -e ."
