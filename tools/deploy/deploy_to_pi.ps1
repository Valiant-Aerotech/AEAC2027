param(
    [Parameter(Mandatory = $true)]
    [string]$PiHost,
    [string]$RemoteDir = "~/AEAC2027"
)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "..\lib\script_paths.ps1")
$ctx = Initialize-ValiantScript -ScriptRoot $PSScriptRoot
$Root = $ctx.RepoRoot

if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Show-ValiantFailure "ssh not found on PATH" -Hints @(
        "Install OpenSSH client (Windows Settings -> Apps -> Optional features)",
        "Or use Git for Windows ssh"
    )
}

Write-Host "Deploying repo to ${PiHost}:${RemoteDir} ..."
try {
    ssh $PiHost "mkdir -p $RemoteDir"
    if ($LASTEXITCODE -ne 0) {
        Show-ValiantFailure "ssh mkdir failed (exit $LASTEXITCODE)" -Hints @(
            "Check PiHost: $PiHost",
            "Test: ssh $PiHost echo ok"
        )
    }
    scp -r src config hardware missions pyproject.toml README.md "${PiHost}:${RemoteDir}/"
    if ($LASTEXITCODE -ne 0) {
        Show-ValiantFailure "scp failed (exit $LASTEXITCODE)" -Hints @(
            "Check network and SSH key",
            "Test: ssh $PiHost"
        )
    }
}
catch {
    Show-ValiantFailure "Deploy failed: $($_.Exception.Message)" -Hints @(
        "Verify Pi is online and PiHost is correct"
    )
}

if (Test-Path "models\best.onnx") {
    ssh $PiHost "mkdir -p $RemoteDir/models"
    scp models\best.onnx "${PiHost}:${RemoteDir}/models/"
    Write-Host "Deployed models/best.onnx"
} else {
    Write-ValiantWarn "models\best.onnx not found locally (optional for Pi CV)"
}

if (Test-Path "config\vion_calibration.yaml") {
    scp config\vion_calibration.yaml "${PiHost}:${RemoteDir}/config/"
}

Write-Host "Done. On Pi: cd $RemoteDir && pip install -e ."
