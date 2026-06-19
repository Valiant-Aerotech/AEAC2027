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
    wsl -d $Distro bash -lc $cmd
    return $LASTEXITCODE
}

function Test-ValiantSitlBuilt {
    param([Parameter(Mandatory = $true)][string]$DistroName)
    wsl -d $DistroName bash -lc "test -x ~/ardupilot/build/sitl/bin/arducopter" 2>$null | Out-Null
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
    wsl -d $Distro bash -lc "tail -25 $LastLog 2>/dev/null || echo '(none)'"
    Write-Host ""
    Write-Host "Last setup log:" -ForegroundColor Yellow
    wsl -d $Distro bash -lc "tail -25 $SetupLog 2>/dev/null || echo '(none)'"
    Write-Host ""
    Write-Host "Last build log:" -ForegroundColor Yellow
    wsl -d $Distro bash -lc "tail -15 $BuildLog 2>/dev/null || echo '(none)'"
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
    $argSuffix = ""
    if ($ExtraBashArgs.Count -gt 0) {
        $quoted = ($ExtraBashArgs | ForEach-Object {
            if ($_ -match '\s') { "'$($_ -replace "'", "'\\''")'" } else { $_ }
        }) -join ' '
        $argSuffix = " $quoted"
    }
    # Use a single-quoted PS string so bash vars ($TMP, ${PIPESTATUS[0]}) are not expanded by PowerShell.
    $bashCmd = 'set -o pipefail; TMP=$(mktemp); sed ''s/\r$//'' ''' + $WslScript + ''' > "$TMP"; bash "$TMP"' + $argSuffix + ' 2>&1 | tee -a ' + $LogFile + '; ec=${PIPESTATUS[0]}; rm -f "$TMP"; exit $ec'
    $code = Invoke-ValiantWslBashLc -Distro $distro -Command $bashCmd

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
