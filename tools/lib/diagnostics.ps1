# Shared error handling and diagnostics for Valiant PowerShell scripts (ASCII-only).
# Usage from tools\*.ps1:  . (Join-Path $PSScriptRoot "lib\diagnostics.ps1")

$script:ValiantDiagLibDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:ValiantToolsDir = Split-Path -Parent $script:ValiantDiagLibDir

function Get-ValiantToolsDir {
    return $script:ValiantToolsDir
}

function Write-ValiantError {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "ERROR: $Message" -ForegroundColor Red
}

function Write-ValiantHint {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "  -> $Message" -ForegroundColor Yellow
}

function Write-ValiantWarn {
    param([Parameter(Mandatory = $true)][string]$Message)
    Write-Host "WARN: $Message" -ForegroundColor Yellow
}

function Show-ValiantFailure {
    param(
        [Parameter(Mandatory = $true)][string]$What,
        [string[]]$Hints = @(),
        [string]$Doc = "",
        [int]$ExitCode = 1,
        [switch]$NoExit
    )
    Write-Host ""
    Write-ValiantError $What
    foreach ($h in $Hints) {
        Write-ValiantHint $h
    }
    if ($Doc) {
        Write-ValiantHint "Docs: $Doc"
    }
    Write-ValiantHint "Full check: python tools\valiant.py diagnose"
    if (-not $NoExit) {
        exit $ExitCode
    }
}

function Assert-ValiantFile {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [string]$Purpose = "required file",
        [string[]]$Hints = @()
    )
    if (-not (Test-Path -LiteralPath $Path)) {
        $allHints = @("Expected: $Path") + $Hints
        Show-ValiantFailure "Missing $Purpose" -Hints $allHints
    }
}

function Invoke-ValiantPythonStep {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string[]]$Arguments,
        [string[]]$Hints = @(),
        [switch]$AllowFail
    )
    Write-Host "--- $Label ---" -ForegroundColor Yellow
    & @Arguments
    $rc = $LASTEXITCODE
    if ($rc -ne 0 -and -not $AllowFail) {
        $stepHints = @("Command: $($Arguments -join ' ')") + $Hints
        Show-ValiantFailure "$Label failed (exit $rc)" -Hints $stepHints
    }
    return $rc
}

function ConvertTo-ValiantUnixShell {
    param([Parameter(Mandatory = $true)][string]$Text)
    return ($Text -replace "`r`n", "`n" -replace "`r", "`n").Trim()
}

function Invoke-ValiantWslBashLc {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [string]$Distro = ""
    )
    if (-not $Distro) {
        . (Join-Path $script:ValiantToolsDir "wsl_distro.ps1")
        $Distro = Get-ValiantWslDistro
    }
    if (-not $Distro) {
        throw "No Ubuntu WSL distro found. Run: wsl -l -v"
    }
    $cmd = ConvertTo-ValiantUnixShell -Text $Command
    # Pass -lc script as a single argument; unquoted wsl bash -lc $cmd re-parses
    # semicolons and expands nested $TMP / $ec in PowerShell.
    return (Invoke-ValiantWsl -Distro $Distro -WslArgs @('bash', '-lc', $cmd))
}

function Install-ValiantWslRunner {
    param([Parameter(Mandatory = $true)][string]$Distro)
    $runnerWin = Join-Path $script:ValiantToolsDir "sitl\wsl_run.sh"
    Assert-ValiantFile -Path $runnerWin -Purpose "WSL runner script"
    $runnerWsl = (wsl -d $Distro wslpath -a $runnerWin).Trim()
    $installCmd = ConvertTo-ValiantUnixShell -Text @"
mkdir -p ~/.valiant/bin && sed 's/\r$//' '$runnerWsl' > ~/.valiant/bin/wsl_run.sh && chmod +x ~/.valiant/bin/wsl_run.sh
"@
    $code = Invoke-ValiantWsl -Distro $Distro -WslArgs @('bash', '-lc', $installCmd)
    if ($code -ne 0) {
        throw "Failed to install WSL runner (~/.valiant/bin/wsl_run.sh)"
    }
}

function Get-ValiantWslRunnerPath {
    param([Parameter(Mandatory = $true)][string]$Distro)
    $code = Invoke-ValiantWsl -Distro $Distro -WslArgs @('bash', '-lc', 'test -x ~/.valiant/bin/wsl_run.sh')
    if ($code -ne 0) {
        Install-ValiantWslRunner -Distro $Distro
    }
    return '~/.valiant/bin/wsl_run.sh'
}

function Test-ValiantSitlBuilt {
    param([Parameter(Mandatory = $true)][string]$DistroName)
    Invoke-ValiantWsl -Distro $DistroName -WslArgs @('bash', '-lc', 'test -x ~/ardupilot/build/sitl/bin/arducopter') | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Show-WslSitlDiagnostics {
    param(
        [Parameter(Mandatory = $true)][string]$Distro,
        [Parameter(Mandatory = $true)][string]$Context,
        [string]$SetupLog = "~/.valiant_sitl_setup.log",
        [string]$BuildLog = "~/.valiant_sitl_build.log",
        [string]$LastLog = "~/.valiant_wsl_last.log"
    )
    Write-Host ""
    Write-ValiantError $Context
    Write-Host ""
    Write-Host "WSL status ($Distro):" -ForegroundColor Yellow
    Invoke-ValiantWslBashLc -Distro $Distro -Command @"
echo -n '  arducopter binary: '; test -x ~/ardupilot/build/sitl/bin/arducopter && echo OK || echo MISSING
echo -n '  ardupilot clone:   '; test -d ~/ardupilot/.git && echo OK || echo MISSING
echo -n '  venv-ardupilot:    '; test -f ~/venv-ardupilot/bin/activate && echo OK || echo MISSING
echo -n '  prereqs marker:    '; test -f ~/.valiant_ardupilot_prereqs_done && echo OK || echo MISSING
echo -n '  build marker:      '; test -f ~/.valiant_ardupilot_sitl_built && echo OK || echo MISSING
"@
    Write-Host ""
    Write-Host "Last WSL script log:" -ForegroundColor Yellow
    Invoke-ValiantWsl -Distro $Distro -WslArgs @('bash', '-lc', "tail -25 $LastLog 2>/dev/null || echo '(none)'")
    Write-Host ""
    Write-Host "Last setup log:" -ForegroundColor Yellow
    Invoke-ValiantWsl -Distro $Distro -WslArgs @('bash', '-lc', "tail -25 $SetupLog 2>/dev/null || echo '(none)'")
    Write-Host ""
    Write-Host "Last build log:" -ForegroundColor Yellow
    Invoke-ValiantWsl -Distro $Distro -WslArgs @('bash', '-lc', "tail -15 $BuildLog 2>/dev/null || echo '(none)'")
    Write-ValiantHint "Docs: docs\runbooks\sitl-wsl.md"
    Write-ValiantHint "Run: python tools\valiant.py diagnose"
}

function Invoke-ValiantWslBashScript {
    param(
        [Parameter(Mandatory = $true)][string]$WinScriptPath,
        [string]$LogFile = "~/.valiant_wsl_last.log",
        [string]$FailureContext = "WSL script failed",
        [string[]]$Hints = @(),
        [string[]]$ExtraBashArgs = @(),
        [switch]$TreatSitlBuiltAsSuccess
    )

    . (Join-Path $script:ValiantToolsDir "wsl_distro.ps1")

    if (-not (Test-ValiantWslReady)) {
        Show-ValiantFailure "WSL Ubuntu not ready" -Hints @(
            "Run: .\tools\setup_wsl.ps1",
            "Open Ubuntu from Start menu once (finish Linux username/password)"
        ) -Doc "docs\runbooks\sitl-wsl.md"
    }

    $distro = Get-ValiantWslDistro
    Assert-ValiantFile -Path $WinScriptPath -Purpose "WSL bash script"

    $ShForward = $WinScriptPath -replace '\\', '/'
    $WslScript = (wsl -d $distro wslpath -a $ShForward).Trim()
    $runner = Get-ValiantWslRunnerPath -Distro $distro
    $wslArgs = @('bash', $runner, $WslScript, $LogFile)
    if ($ExtraBashArgs.Count -gt 0) {
        $wslArgs += $ExtraBashArgs
    }
    $code = Invoke-ValiantWsl -Distro $distro -WslArgs $wslArgs

    if ($code -ne 0 -and $TreatSitlBuiltAsSuccess -and (Test-ValiantSitlBuilt -DistroName $distro)) {
        Write-ValiantWarn "Exit code $code but arducopter is built; continuing."
        return 0
    }
    if ($code -ne 0) {
        Show-WslSitlDiagnostics -Distro $distro -Context "$FailureContext (exit $code)" -LastLog $LogFile
        foreach ($h in $Hints) {
            Write-ValiantHint $h
        }
        exit $code
    }
    return 0
}

function Invoke-ValiantMissionPython {
    param(
        [Parameter(Mandatory = $true)][string[]]$MissionArgs,
        [string]$Label = "SITL mission"
    )
    $env:PYTHONPATH = "src"
    Write-Host "$Label`: python $($MissionArgs -join ' ')"
    python @MissionArgs
    $rc = $LASTEXITCODE
    if ($rc -ne 0) {
        Show-ValiantFailure "$Label failed (exit $rc)" -Hints @(
            "Is SITL running? Terminal 1: .\tools\launch_sitl.ps1",
            "Wait for SERIAL0 on TCP port 5760 before starting mission",
            "Warm retry: .\tools\run_sitl_mission.ps1 -SkipPreflight"
        ) -Doc "docs\runbooks\sitl-wsl.md"
    }
}
