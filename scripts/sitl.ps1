# Start PX4 SITL in this tab, and open the other services as tabs in this window.
# Run from Windows Terminal: .\scripts\sitl.ps1
# The home exports last for this launch only. default.sdf is not changed.
# A simulator that is already running is left in place. Its home does not move.

param(
    [switch]$CheckOnly,
    [Alias('ForceCheck')]
    [switch]$Recheck
)

$Repo = '/mnt/a/Code/Valiant-Aerotech/AEAC2027'
$PreflightCache = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'AEAC2027\sitl-preflight.json'

$Sites = [ordered]@{
    '1' = @{
        Name = 'AEAC Comp Test Site'
        Lat  = '50.09676'
        Lon  = '-110.73595'
        Alt  = '719.4'
    }
    '2' = @{
        Name = 'MUN Engg Parking Lot'
        Lat  = '47.576151'
        Lon  = '-52.734118'
        Alt  = '52.1'
    }
    '3' = @{
        Name = 'Pouch Cove Test Site'
        Lat  = '47.73591'
        Lon  = '-52.728668'
        Alt  = '80.1'
    }
}

function Invoke-Wsl {
    param([Parameter(Mandatory = $true)][string]$Bash)
    & wsl.exe -d Ubuntu-24.04 -e bash -lc $Bash
    return $LASTEXITCODE
}

function Test-WslCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Checker,
        [Parameter(Mandatory = $true)][string]$Needle
    )
    & wsl.exe -d Ubuntu-24.04 -e bash $Checker $Needle
    return $LASTEXITCODE -eq 0
}

function Write-BashFile {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Body
    )
    $path = Join-Path $env:TEMP $Name
    $unix = ($Body -replace "`r`n", "`n") -replace "`r", "`n"
    if (-not $unix.EndsWith("`n")) {
        $unix += "`n"
    }
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($path, $unix, $utf8)
    $full = [System.IO.Path]::GetFullPath($path)
    if ($full -notmatch '^([A-Za-z]):\\(.*)$') {
        throw "Cannot map $full into WSL."
    }
    return ('/mnt/{0}/{1}' -f $Matches[1].ToLower(), ($Matches[2] -replace '\\', '/'))
}

function Invoke-WslRepair {
    param([string]$ScriptPath)

    & wsl.exe -d Ubuntu-24.04 -e bash $ScriptPath 2>&1
}

function New-PreflightResult {
    param(
        [Parameter(Mandatory = $true)][string]$Id,
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][ValidateSet('required', 'warning')][string]$Severity,
        [Parameter(Mandatory = $true)][ValidateSet('pass', 'fail', 'warn')][string]$Status,
        [Parameter(Mandatory = $true)][string]$Detail,
        [string[]]$AptPackages = @(),
        [string]$Repair = ''
    )
    return [pscustomobject]@{
        Id          = $Id
        Label       = $Label
        Severity    = $Severity
        Status      = $Status
        Detail      = $Detail
        AptPackages = @($AptPackages)
        Repair      = $Repair
    }
}

function Test-PreflightCache {
    if (-not (Test-Path -LiteralPath $PreflightCache -PathType Leaf)) {
        return $false
    }
    try {
        $cached = Get-Content -LiteralPath $PreflightCache -Raw | ConvertFrom-Json
        return $cached.Version -eq 1 -and $cached.Ready -eq $true
    }
    catch {
        return $false
    }
}

function Set-PreflightCache {
    param([Parameter(Mandatory = $true)][bool]$Ready)

    if (-not $Ready) {
        Remove-Item -LiteralPath $PreflightCache -Force -ErrorAction SilentlyContinue
        return
    }

    $cacheDirectory = Split-Path -Parent $PreflightCache
    New-Item -ItemType Directory -Path $cacheDirectory -Force | Out-Null
    [pscustomobject]@{
        Version   = 1
        Ready     = $true
        CheckedAt = [DateTimeOffset]::UtcNow.ToString('o')
    } | ConvertTo-Json | Set-Content -LiteralPath $PreflightCache -Encoding UTF8
}

function Write-PreflightSummary {
    param([Parameter(Mandatory = $true)][object[]]$Results)

    Write-Host ''
    Write-Host 'SITL prerequisite check'
    foreach ($result in $Results) {
        $prefix = switch ($result.Status) {
            'pass' { '[PASS]' }
            'warn' { '[WARN]' }
            default { '[FAIL]' }
        }
        $color = switch ($result.Status) {
            'pass' { 'Green' }
            'warn' { 'Yellow' }
            default { 'Red' }
        }
        Write-Host ('{0,-7} {1}: {2}' -f $prefix, $result.Label, $result.Detail) -ForegroundColor $color
        if ($result.Status -ne 'pass' -and $result.Repair) {
            Write-Host ('        Repair: {0}' -f $result.Repair) -ForegroundColor DarkGray
        }
    }

    $requiredFailures = @($Results | Where-Object {
        $_.Severity -eq 'required' -and $_.Status -eq 'fail'
    })
    $warnings = @($Results | Where-Object { $_.Status -eq 'warn' })
    Write-Host ('Summary: {0} required failure(s), {1} warning(s).' -f $requiredFailures.Count, $warnings.Count)
    return $requiredFailures.Count -eq 0
}

function Get-HostPreflightResults {
        $results = [System.Collections.Generic.List[object]]::new()

        $wt = Get-Command wt.exe -ErrorAction SilentlyContinue
        $results.Add((New-PreflightResult -Id 'host.windows-terminal' -Label 'Windows Terminal' -Severity 'required' `
                -Status $(if ($wt) { 'pass' } else { 'fail' }) `
                -Detail $(if ($wt) { 'wt.exe is available.' } else { 'wt.exe was not found.' }) `
                -Repair 'Install Windows Terminal from the Microsoft Store or winget.'))

        $wsl = Get-Command wsl.exe -ErrorAction SilentlyContinue
        $results.Add((New-PreflightResult -Id 'host.wsl' -Label 'WSL' -Severity 'required' `
                -Status $(if ($wsl) { 'pass' } else { 'fail' }) `
                -Detail $(if ($wsl) { 'wsl.exe is available.' } else { 'wsl.exe was not found.' }) `
                -Repair 'Enable WSL 2 and install Ubuntu 24.04.'))
        if (-not $wsl) {
                return @($results)
        }

        $rawDistros = (& wsl.exe --list --verbose 2>$null) -join "`n"
        $distroText = $rawDistros -replace "`0", ''
        $ubuntuLine = @($distroText -split "`r?`n" | Where-Object { $_ -match 'Ubuntu-24\.04' } | Select-Object -First 1)
        $hasUbuntu = $ubuntuLine.Count -gt 0
        $results.Add((New-PreflightResult -Id 'host.ubuntu' -Label 'Ubuntu 24.04' -Severity 'required' `
                -Status $(if ($hasUbuntu) { 'pass' } else { 'fail' }) `
                -Detail $(if ($hasUbuntu) { 'Ubuntu-24.04 is registered.' } else { 'Ubuntu-24.04 is not registered.' }) `
                -Repair 'Run: wsl --install -d Ubuntu-24.04'))
        if (-not $hasUbuntu) {
                return @($results)
        }

        $isVersion2 = $ubuntuLine[0] -match '\s2\s*$'
        $results.Add((New-PreflightResult -Id 'host.wsl-version' -Label 'WSL version' -Severity 'required' `
                -Status $(if ($isVersion2) { 'pass' } else { 'fail' }) `
                -Detail $(if ($isVersion2) { 'Ubuntu-24.04 uses WSL 2.' } else { 'Ubuntu-24.04 is not using WSL 2.' }) `
                -Repair 'Run: wsl --set-version Ubuntu-24.04 2'))
        return @($results)
}

function Get-WslPreflightResults {
        $probe = Write-BashFile -Name 'aeac-preflight.sh' -Body @'
set +e

emit() {
    local id="$1" label="$2" severity="$3" status="$4" detail="$5" packages="$6" repair="$7"
    printf 'AEAC_PREFLIGHT|%s|%s|%s|%s|%s|%s|%s\n' \
        "$id" \
        "$(printf '%s' "$label" | base64 -w0)" \
        "$severity" "$status" \
        "$(printf '%s' "$detail" | base64 -w0)" \
        "$(printf '%s' "$packages" | base64 -w0)" \
        "$(printf '%s' "$repair" | base64 -w0)"
}

check_command() {
    local command="$1" label="$2" severity="$3" package="$4"
    if command -v "$command" >/dev/null 2>&1; then
        emit "wsl.command.$command" "$label" "$severity" pass "$command is available." '' ''
    else
        local status=fail
        [ "$severity" = warning ] && status=warn
        emit "wsl.command.$command" "$label" "$severity" "$status" "$command is not available." "$package" "Install $package in Ubuntu-24.04."
    fi
}

REPO='/mnt/a/Code/Valiant-Aerotech/AEAC2027'
if [ -d "$REPO/src" ] && [ -f "$REPO/src/telemetry/package.xml" ]; then
    emit wsl.repo 'Repository' required pass 'The repository is accessible from WSL.' '' ''
else
    emit wsl.repo 'Repository' required fail 'The repository or its src tree is not accessible from WSL.' '' 'Verify the A: drive mount and repository path.'
fi

[ -f /opt/ros/jazzy/setup.bash ] && source /opt/ros/jazzy/setup.bash >/dev/null 2>&1

check_command python3 Python required python3
check_command colcon colcon required python3-colcon-common-extensions
check_command ros2 'ROS 2 CLI' required ros-jazzy-ros-base
check_command make make required build-essential
check_command gz 'Gazebo CLI' required gz-harmonic
check_command MicroXRCEAgent 'Micro XRCE-DDS Agent' required micro-xrce-dds-agent
check_command rosdep rosdep warning python3-rosdep
if command -v python3 >/dev/null 2>&1 && python3 -c 'import pymavlink' >/dev/null 2>&1; then
    emit wsl.python.pymavlink pymavlink warning pass 'The pymavlink Python module is importable.' '' ''
else
    emit wsl.python.pymavlink pymavlink warning warn 'The pymavlink Python module is not importable.' python3-pymavlink 'Install python3-pymavlink in Ubuntu-24.04.'
fi

if [ -f /opt/ros/jazzy/setup.bash ]; then
    emit wsl.ros-jazzy 'ROS Jazzy' required pass '/opt/ros/jazzy/setup.bash exists.' '' ''
else
    emit wsl.ros-jazzy 'ROS Jazzy' required fail '/opt/ros/jazzy/setup.bash is missing.' ros-jazzy-ros-base 'Install ROS 2 Jazzy.'
fi

if [ -f "$HOME/ros2_px4_ws/install/setup.bash" ]; then
    emit wsl.px4-overlay 'PX4 ROS overlay' required pass 'The PX4 ROS workspace overlay exists.' '' ''
else
    emit wsl.px4-overlay 'PX4 ROS overlay' required fail '$HOME/ros2_px4_ws/install/setup.bash is missing.' '' 'Build the ros2_px4_ws overlay containing px4_msgs.'
fi

if [ -d "$HOME/PX4-Autopilot" ] && [ -f "$HOME/PX4-Autopilot/Makefile" ]; then
    emit wsl.px4-source 'PX4 Autopilot' required pass '$HOME/PX4-Autopilot is present.' '' ''
else
    emit wsl.px4-source 'PX4 Autopilot' required fail '$HOME/PX4-Autopilot is missing or incomplete.' '' 'Clone and provision PX4-Autopilot in the WSL home directory.'
fi

if command -v gz >/dev/null 2>&1 && gz sim --versions 2>/dev/null | grep -Eq '(^|[^0-9])8\.'; then
    emit wsl.gazebo-version 'Gazebo Harmonic' required pass 'Gazebo Sim major version 8 is available.' '' ''
else
    emit wsl.gazebo-version 'Gazebo Harmonic' required fail 'Gazebo Sim major version 8 was not detected.' gz-harmonic 'Install Gazebo Harmonic.'
fi

if command -v MicroXRCEAgent >/dev/null 2>&1; then
    xrce_version_file='/usr/local/share/microxrcedds_agent/cmake/microxrcedds_agentConfigVersion.cmake'
    if { [ -f "$xrce_version_file" ] && grep -Eq 'PACKAGE_VERSION[^0-9]+"?2\.4\.3"?' "$xrce_version_file"; } || \
       find /usr/local/lib -maxdepth 1 -name 'libmicroxrcedds_agent.so.2.4.3' -print -quit 2>/dev/null | grep -q .; then
        emit wsl.xrce-version 'XRCE version' required pass 'Micro XRCE-DDS Agent 2.4.3 is available.' '' ''
    else
        emit wsl.xrce-version 'XRCE version' required fail 'Micro XRCE-DDS Agent 2.4.3 was not detected.' '' 'Install Micro XRCE-DDS Agent 2.4.3.'
    fi
fi

if [ -f /opt/ros/jazzy/setup.bash ] && [ -f "$HOME/ros2_px4_ws/install/setup.bash" ]; then
    source /opt/ros/jazzy/setup.bash >/dev/null 2>&1
    source "$HOME/ros2_px4_ws/install/setup.bash" >/dev/null 2>&1
    [ -f "$REPO/install/setup.bash" ] && source "$REPO/install/setup.bash" >/dev/null 2>&1

    if ros2 pkg prefix px4_msgs >/dev/null 2>&1; then
        emit wsl.px4-msgs px4_msgs required pass 'The px4_msgs ROS package is discoverable.' '' ''
    else
        emit wsl.px4-msgs px4_msgs required fail 'The px4_msgs ROS package is not discoverable.' '' 'Build and source the ros2_px4_ws overlay.'
    fi

    if ros2 pkg prefix telemetry >/dev/null 2>&1 && ros2 pkg prefix offboard >/dev/null 2>&1; then
        emit wsl.workspace-overlay 'AEAC ROS overlay' required pass 'telemetry and offboard are discoverable.' '' ''
    else
        emit wsl.workspace-overlay 'AEAC ROS overlay' required fail 'telemetry or offboard is not discoverable.' '' 'Run colcon build --symlink-install in the repository.'
    fi

    if ros2 pkg prefix ros_gz_sim >/dev/null 2>&1; then
        emit wsl.ros-gz ros_gz warning pass 'ros_gz_sim is discoverable.' '' ''
    else
        emit wsl.ros-gz ros_gz warning warn 'ros_gz_sim is not discoverable.' ros-jazzy-ros-gz 'Install ros-jazzy-ros-gz if ROS/Gazebo bridges are needed.'
    fi
fi

if command -v python3 >/dev/null 2>&1; then
    if PYTHONPATH="$REPO/src/telemetry${PYTHONPATH:+:$PYTHONPATH}" python3 -c 'import rclpy; from px4_msgs import msg; import telemetry; import websocket' >/dev/null 2>&1; then
        emit wsl.python-imports 'Python ROS imports' required pass 'rclpy, px4_msgs, telemetry, and websocket import successfully.' '' ''
    else
        emit wsl.python-imports 'Python ROS imports' required fail 'One or more required Python imports failed.' python3-websocket 'Source the ROS overlays, build the workspace, and install python3-websocket.'
    fi

    config_state="$(cd "$REPO" && PYTHONPATH="$REPO/src/telemetry${PYTHONPATH:+:$PYTHONPATH}" python3 -c 'from telemetry.secrets import competition_secrets; s=competition_secrets(); print("configured" if s.token and s.url and s.uav_id else "missing")' 2>/dev/null)"
    if [ "$config_state" = configured ]; then
        emit wsl.telemetry-config 'Telemetry configuration' required pass 'Competition telemetry credentials are configured.' '' ''
    else
        emit wsl.telemetry-config 'Telemetry configuration' required fail 'Competition telemetry credentials are incomplete.' '' 'Set AEAC_COMP_TOKEN and the required AEAC_COMP_* values in the environment or repository .env file.'
    fi

    clock_state="$(PYTHONPATH="$REPO/src/telemetry${PYTHONPATH:+:$PYTHONPATH}" python3 -c 'from telemetry.clock import clock_is_plausible; print("ok" if clock_is_plausible() else "bad")' 2>/dev/null)"
    if [ "$clock_state" = ok ]; then
        emit wsl.clock 'System clock' required pass 'The UTC clock is plausible for competition telemetry.' '' ''
    else
        emit wsl.clock 'System clock' required fail 'The UTC clock is earlier than the competition plausibility threshold.' '' 'Synchronize the Windows and WSL clocks.'
    fi
fi

if pgrep -f 'QGroundControl' >/dev/null 2>&1 || powershell.exe -NoProfile -Command "if (Get-Process QGroundControl -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }" >/dev/null 2>&1; then
    emit wsl.qgroundcontrol QGroundControl warning pass 'QGroundControl appears to be running.' '' ''
else
    emit wsl.qgroundcontrol QGroundControl warning warn 'QGroundControl does not appear to be running.' '' 'Start QGroundControl before flight operations if it is required.'
fi

if command -v rosdep >/dev/null 2>&1 && [ -d "$REPO/src" ]; then
    cd "$REPO"
    if rosdep check --from-paths src --ignore-src -r >/dev/null 2>&1; then
        emit wsl.rosdep rosdep warning pass 'rosdep reports package dependencies satisfied.' '' ''
    else
        emit wsl.rosdep rosdep warning warn 'rosdep reports missing package dependencies.' '' 'Run rosdep install --from-paths src --ignore-src -r -y.'
    fi
fi
'@

    $lines = [System.Collections.Generic.List[string]]::new()
    $receivedChecks = 0
    & wsl.exe -d Ubuntu-24.04 -e bash $probe 2>$null | ForEach-Object {
        $line = [string]$_
        $lines.Add($line)
        if ($line -like 'AEAC_PREFLIGHT|*') {
            $receivedChecks++
            Write-Progress -Id 1 -Activity 'Checking SITL prerequisites' `
                -Status ("WSL check {0} completed" -f $receivedChecks) `
                -PercentComplete ([Math]::Min(95, 20 + ($receivedChecks * 4)))
        }
    }
        if ($LASTEXITCODE -ne 0 -and -not ($lines | Where-Object { $_ -like 'AEAC_PREFLIGHT|*' })) {
                return @(New-PreflightResult -Id 'wsl.probe' -Label 'WSL prerequisite probe' -Severity 'required' -Status 'fail' `
                        -Detail 'The WSL prerequisite probe did not complete.' -Repair 'Run the script again after confirming Ubuntu-24.04 starts normally.')
        }

        $results = [System.Collections.Generic.List[object]]::new()
        foreach ($line in $lines) {
                if ($line -notlike 'AEAC_PREFLIGHT|*') { continue }
                $parts = $line -split '\|', 8
                if ($parts.Count -ne 8) { continue }
                try {
                        $decode = { param($value) [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($value)) }
                        $packageText = & $decode $parts[6]
                        $packages = @($packageText -split ',' | Where-Object { $_ })
                        $results.Add((New-PreflightResult -Id $parts[1] -Label (& $decode $parts[2]) -Severity $parts[3] `
                                -Status $parts[4] -Detail (& $decode $parts[5]) -AptPackages $packages -Repair (& $decode $parts[7])))
                }
                catch {
                        return @(New-PreflightResult -Id 'wsl.probe-output' -Label 'WSL prerequisite probe' -Severity 'required' -Status 'fail' `
                                -Detail 'The WSL prerequisite probe returned malformed output.' -Repair 'Run the script again and inspect the WSL environment.')
                }
        }
        if ($results.Count -eq 0) {
                return @(New-PreflightResult -Id 'wsl.probe-output' -Label 'WSL prerequisite probe' -Severity 'required' -Status 'fail' `
                        -Detail 'The WSL prerequisite probe returned no check records.' -Repair 'Run the script again and inspect the WSL environment.')
        }
        return @($results)
}

function Invoke-SitlPreflight {
    Write-Progress -Id 1 -Activity 'Checking SITL prerequisites' -Status 'Checking Windows and WSL' -PercentComplete 5
    try {
        $results = @(Get-HostPreflightResults)
        $hostReady = -not ($results | Where-Object { $_.Severity -eq 'required' -and $_.Status -eq 'fail' })
        if ($hostReady) {
            Write-Progress -Id 1 -Activity 'Checking SITL prerequisites' -Status 'Checking Ubuntu environment' -PercentComplete 20
            $results += @(Get-WslPreflightResults)
        }
        $ready = Write-PreflightSummary -Results $results
        return [pscustomobject]@{ Ready = $ready; Results = $results }
    }
    finally {
        Write-Progress -Id 1 -Activity 'Checking SITL prerequisites' -Completed
        }
}

function Invoke-PreflightRepair {
    param(
        [Parameter(Mandatory = $true)][object[]]$Results,
        [scriptblock]$RepairRunner = { param($ScriptPath) Invoke-WslRepair -ScriptPath $ScriptPath }
    )

    $unhealthy = @($Results | Where-Object { $_.Status -ne 'pass' })
    $packages = @($unhealthy | ForEach-Object { $_.AptPackages } | Where-Object {
        $_ -and $_ -match '^[a-z0-9][a-z0-9+.-]*$'
    } | Sort-Object -Unique)
    $repairRosdep = @($unhealthy | Where-Object { $_.Id -eq 'wsl.rosdep' }).Count -gt 0
    if ($packages.Count -eq 0 -and -not $repairRosdep) {
        return $false
    }

    Write-Host ''
    Write-Host 'Optional WSL repair is available:' -ForegroundColor Yellow
    if ($packages.Count -gt 0) {
        Write-Host ('  apt packages: {0}' -f ($packages -join ', '))
    }
    if ($repairRosdep) {
        Write-Host '  provision repository dependencies with rosdep'
    }
    if ([Console]::IsInputRedirected) {
        Write-Host 'Repair skipped because input is redirected.' -ForegroundColor DarkGray
        return $false
    }
    $answer = Read-Host 'Run this repair now? [y/N]'
    if ($answer -notmatch '^(?i:y|yes)$') {
        Write-Host 'Repair skipped.' -ForegroundColor DarkGray
        return $false
    }

    $packageList = $packages -join ' '
    $repairBody = @"
set -e
REPO='$Repo'
if [ -n '$packageList' ]; then
    printf 'AEAC_REPAIR|Updating apt package metadata\n'
  sudo apt-get update
    printf 'AEAC_REPAIR|Installing prerequisite packages\n'
  sudo apt-get install -y $packageList
fi
if [ '$($repairRosdep.ToString().ToLowerInvariant())' = true ]; then
    printf 'AEAC_REPAIR|Installing repository dependencies with rosdep\n'
  source /opt/ros/jazzy/setup.bash
  [ -f "`$HOME/ros2_px4_ws/install/setup.bash" ] && source "`$HOME/ros2_px4_ws/install/setup.bash"
  cd "`$REPO"
  rosdep install --from-paths src --ignore-src -r -y
fi
"@
    $repairScript = Write-BashFile -Name 'aeac-preflight-repair.sh' -Body $repairBody
    Write-Host 'Repair started. WSL output will appear below; sudo may prompt for your password.' -ForegroundColor Cyan
    Write-Progress -Id 2 -Activity 'Repairing SITL prerequisites' -Status 'Starting WSL repair' -PercentComplete 5
    try {
        & $RepairRunner $repairScript | ForEach-Object {
            $line = [string]$_
            if ($line -like 'AEAC_REPAIR|*') {
                $stage = $line.Substring('AEAC_REPAIR|'.Length)
                $percent = if ($stage -like 'Updating*') { 20 } elseif ($stage -like 'Installing prerequisite*') { 55 } else { 80 }
                Write-Host $stage -ForegroundColor Cyan
                Write-Progress -Id 2 -Activity 'Repairing SITL prerequisites' -Status $stage -PercentComplete $percent
            }
            else {
                Write-Host $line
            }
        }
        $repairExitCode = $LASTEXITCODE
    }
    finally {
        Write-Progress -Id 2 -Activity 'Repairing SITL prerequisites' -Completed
    }
    if ($repairExitCode -ne 0) {
        Write-Host 'Repair did not complete successfully.' -ForegroundColor Red
    }
    return $true
}

function Start-WslTab {
    param(
        [Parameter(Mandatory = $true)][string]$Title,
        [Parameter(Mandatory = $true)][string]$Body
    )
    $wslPath = Write-BashFile -Name "aeac-$Title.sh" -Body $Body
    & wt.exe -w 0 new-tab --title $Title -- wsl.exe -d Ubuntu-24.04 -e bash $wslPath | Out-Null
    if ($LASTEXITCODE -ne 0) {
        return $false
    }
    return $true
}

function Write-SiteMenuOption {
    param(
        [Parameter(Mandatory = $true)][int]$Index,
        [Parameter(Mandatory = $true)][int]$SelectedIndex,
        [Parameter(Mandatory = $true)][int]$Top,
        [Parameter(Mandatory = $true)][int]$Pad,
        [Parameter(Mandatory = $true)][string[]]$Keys
    )

    [Console]::SetCursorPosition(0, $Top + 2 + $Index)
    $inverseFg = [Console]::BackgroundColor
    $inverseBg = [Console]::ForegroundColor
    $key = $Keys[$Index]
    $label = ('  {0}. {1}' -f $key, $Sites[$key].Name)
    if ($label.Length -gt $Pad) {
        $label = $label.Substring(0, $Pad)
    }
    $label = $label.PadRight($Pad)
    if ($Index -eq $SelectedIndex) {
        Write-Host $label -NoNewline -ForegroundColor $inverseFg -BackgroundColor $inverseBg
    }
    else {
        Write-Host $label -NoNewline
    }
}

function Show-SiteMenu {
    param(
        [Parameter(Mandatory = $true)][int]$Index,
        [Parameter(Mandatory = $true)][int]$Top,
        [Parameter(Mandatory = $true)][int]$Pad,
        [Parameter(Mandatory = $true)][string[]]$Keys,
        [int]$PreviousIndex = -1
    )

    if ($PreviousIndex -lt 0) {
        [Console]::SetCursorPosition(0, $Top)
        Write-Host 'SITL'
        Write-Host ''
        for ($i = 0; $i -lt $Keys.Count; $i++) {
            Write-SiteMenuOption -Index $i -SelectedIndex $Index -Top $Top -Pad $Pad -Keys $Keys
        }
        [Console]::SetCursorPosition(0, $Top + 2 + $Keys.Count)
        Write-Host '  Arrow keys to move, Enter to start' -NoNewline
    }
    else {
        Write-SiteMenuOption -Index $PreviousIndex -SelectedIndex $Index -Top $Top -Pad $Pad -Keys $Keys
        Write-SiteMenuOption -Index $Index -SelectedIndex $Index -Top $Top -Pad $Pad -Keys $Keys
    }
    [Console]::SetCursorPosition(0, $Top + 3 + $Keys.Count)
}

function Read-SiteNumber {
    Write-Host 'This console cannot read arrow keys. Enter 1, 2, or 3.'
    $picked = ''
    while (-not $Sites.Contains($picked)) {
        $picked = Read-Host 'Enter 1, 2, or 3'
    }
    return $picked
}

function Select-SiteChoice {
    $keys = @($Sites.Keys)
    try {
        if ([Console]::IsInputRedirected) {
            return Read-SiteNumber
        }
        $pad = [Math]::Max(1, [Console]::BufferWidth - 1)
        Write-Host ''
        $top = [Console]::CursorTop
        $index = 0
        Show-SiteMenu -Index $index -Top $top -Pad $pad -Keys $keys
        while ($true) {
            $press = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
            switch ($press.VirtualKeyCode) {
                38 {
                    if ($index -gt 0) {
                        $previousIndex = $index
                        $index--
                        Show-SiteMenu -Index $index -PreviousIndex $previousIndex -Top $top -Pad $pad -Keys $keys
                    }
                }
                40 {
                    if ($index -lt ($keys.Count - 1)) {
                        $previousIndex = $index
                        $index++
                        Show-SiteMenu -Index $index -PreviousIndex $previousIndex -Top $top -Pad $pad -Keys $keys
                    }
                }
                13 { return $keys[$index] }
            }
        }
    }
    catch {
        return Read-SiteNumber
    }
}

function Write-StatusLine {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$State
    )
    $text = '{0,-16}{1}' -f $Label, $State
    if ($State -eq 'did not open') {
        Write-Host $text -ForegroundColor Red
    }
    elseif ($State -eq 'already running') {
        Write-Host $text -ForegroundColor DarkGray
    }
    else {
        Write-Host $text
    }
}

function Get-RosLaunch {
    param(
        [Parameter(Mandatory = $true)][string]$Package,
        [Parameter(Mandatory = $true)][string]$Run,
        [string]$Note = ''
    )
    $noteStep = ''
    if ($Note) {
        $escaped = $Note -replace "'", "'\''"
        $noteStep = "printf '%s\n' '$escaped'"
    }
    return @"
set -e
trap 'echo "This tab stopped because a command failed."; exec bash' ERR
REPO='$Repo'
cd "`$REPO"
source /opt/ros/jazzy/setup.bash
source "`$HOME/ros2_px4_ws/install/setup.bash"
if [ -f "`$REPO/install/setup.bash" ]; then
  source "`$REPO/install/setup.bash"
fi
if ! ros2 pkg prefix $Package >/dev/null 2>&1; then
  exec 9>/tmp/aeac-colcon.lock
  flock 9
  if [ -f "`$REPO/install/setup.bash" ]; then
    source "`$REPO/install/setup.bash"
  fi
  if ! ros2 pkg prefix $Package >/dev/null 2>&1; then
    colcon build --packages-select telemetry mission offboard --symlink-install
    source "`$REPO/install/setup.bash"
  fi
fi
cd "`$REPO"
$noteStep
exec $Run
"@
}

$processCheck = Write-BashFile -Name 'aeac-process-check.sh' -Body @'
needle=$1
self=$$
pgrep -af . | awk -v self="$self" -v needle="$needle" '$1 != self && $2 != "awk" && index($0, needle) { found = 1 } END { exit found ? 0 : 1 }'
'@

$useCachedPreflight = -not $CheckOnly -and -not $Recheck -and (Test-PreflightCache)
if ($useCachedPreflight) {
    Write-Host 'SITL prerequisites previously passed. Use -Recheck to check them again.' -ForegroundColor DarkGray
}
else {
    Set-PreflightCache -Ready $false
    $preflight = Invoke-SitlPreflight
    if ($CheckOnly) {
        Set-PreflightCache -Ready $preflight.Ready
        if ($preflight.Ready) { exit 0 }
        exit 1
    }
    if (Invoke-PreflightRepair -Results $preflight.Results) {
        Write-Host ''
        Write-Host 'Rechecking prerequisites after repair...'
        $preflight = Invoke-SitlPreflight
    }
    Set-PreflightCache -Ready $preflight.Ready
    if (-not $preflight.Ready) { exit 1 }
}

$Choice = Select-SiteChoice

$Site = $Sites[$Choice]
$px4Running = (Invoke-Wsl 'pgrep -x px4 >/dev/null') -eq 0
$xrceNeeded = (Invoke-Wsl 'pgrep -x MicroXRCEAgent >/dev/null') -ne 0
$xrceOpened = $false
if ($xrceNeeded) {
    $xrceOpened = Start-WslTab -Title 'XRCE' -Body @'
if ! command -v MicroXRCEAgent >/dev/null 2>&1; then
  echo 'MicroXRCEAgent is not on PATH.'
  exec bash
fi
MicroXRCEAgent udp4 -p 8888
echo "MicroXRCEAgent stopped (exit $?)."
exec bash
'@
}

$needTelemetry = -not (Test-WslCommand -Checker $processCheck -Needle 'fc_telemetry')
$needObstacles = -not (Test-WslCommand -Checker $processCheck -Needle 'ros2 run offboard obstacles') -and -not (Test-WslCommand -Checker $processCheck -Needle 'lib/offboard/obstacles')

$telemetryOpened = $false
if ($needTelemetry) {
    $telemetryNote = "Packets are sent after the aircraft is armed. On the Mylonics flight page, set Site to $($Site.Name)."
    $telemetryOpened = Start-WslTab -Title 'fc_telemetry' -Body (Get-RosLaunch -Package 'telemetry' -Run 'ros2 run telemetry fc_telemetry' -Note $telemetryNote)
}

$obstaclesOpened = $false
if ($needObstacles) {
    $obstaclesOpened = Start-WslTab -Title 'obstacles' -Body (Get-RosLaunch -Package 'offboard' -Run 'ros2 run offboard obstacles')
}

function Get-LaunchState {
    param(
        [Parameter(Mandatory = $true)][bool]$Needed,
        [Parameter(Mandatory = $true)][bool]$Opened
    )
    if (-not $Needed) { return 'already running' }
    if ($Opened) { return 'opened' }
    return 'did not open'
}

$mavlinkBody = @"
set -u
BIN="`$HOME/PX4-Autopilot/build/px4_sitl_default/bin"
MAV="`$BIN/px4-mavlink"
LOG=/tmp/aeac-sitl-mavlink.log
: > "`$LOG"
ready=0
for _ in `$(seq 1 90); do
  if [ -x "`$BIN/px4-commander" ] && pgrep -x px4 >/dev/null; then
    out=`$("`$BIN/px4-commander" status 2>&1) || true
    if ! printf '%s\n' "`$out" | grep -Eqi 'failed to connect|could not connect|no such file'; then
      ready=1
      break
    fi
  fi
  sleep 2
done
if [ "`$ready" -ne 1 ]; then
  echo 'PX4 did not answer. MAVLink was not started.' | tee -a "`$LOG"
  exit 1
fi
status=`$("`$MAV" status 2>&1) || true
HOST=`$(ip route | awk '/default/ {print `$3; exit}')
has_ports=0
if printf '%s\n' "`$status" | grep -q '14570' && printf '%s\n' "`$status" | grep -q 'remote port: 14550'; then
  has_ports=1
fi
partner=`$(printf '%s\n' "`$status" | awk -F': ' '/partner IP:/ {print `$2; exit}')
if [ -z "`$HOST" ]; then
  if [ "`$has_ports" -eq 1 ]; then
    echo 'Could not read the Windows host address. The existing MAVLink link was left as it is.' | tee -a "`$LOG"
  else
    echo 'Could not read the Windows host address. MAVLink was not started.' | tee -a "`$LOG"
    exit 1
  fi
elif [ "`$has_ports" -eq 1 ] && { [ -z "`$partner" ] || [ "`$partner" = "`$HOST" ]; }; then
  echo "MAVLink is already sending to `$HOST on UDP port 14550." | tee -a "`$LOG"
else
  if [ "`$has_ports" -eq 1 ]; then
    "`$MAV" stop-all >>"`$LOG" 2>&1 || true
    sleep 1
  fi
  "`$MAV" start -x -u 14570 -r 4000000 -o 14550 -t "`$HOST" >>"`$LOG" 2>&1 || true
  sleep 1
  status=`$("`$MAV" status 2>&1) || true
  if printf '%s\n' "`$status" | grep -q '14570' && printf '%s\n' "`$status" | grep -q 'remote port: 14550'; then
    echo "MAVLink is sending to `$HOST on UDP port 14550." | tee -a "`$LOG"
  else
    echo "MAVLink did not start toward `$HOST." | tee -a "`$LOG"
    exit 1
  fi
fi
params=0
for _ in `$(seq 1 15); do
  if "`$BIN/px4-param" set CP_DIST 2 >>"`$LOG" 2>&1 \
    && "`$BIN/px4-param" set CP_GO_NO_DATA 1 >>"`$LOG" 2>&1 \
    && "`$BIN/px4-param" set MPC_POS_MODE 0 >>"`$LOG" 2>&1 \
    && "`$BIN/px4-param" set ASPD_PRIMARY 0 >>"`$LOG" 2>&1 \
    && "`$BIN/px4-param" set ASPD_FALLBACK 1 >>"`$LOG" 2>&1; then
    params=1
    break
  fi
  sleep 2
done
if [ "`$params" -ne 1 ]; then
  echo 'SITL parameters were not set.' | tee -a "`$LOG"
  exit 1
fi
"@

$mavlinkScript = Write-BashFile -Name 'aeac-mavlink.sh' -Body $mavlinkBody
$mavProcess = Start-Process -FilePath 'wsl.exe' -ArgumentList @(
    '-d', 'Ubuntu-24.04', '-e', 'bash', $mavlinkScript
) -NoNewWindow -PassThru

Write-Host ''
Write-Host $Site.Name
if ($px4Running) {
    Write-Host 'A simulator is already running. This site will not apply until you type shutdown on its pxh> prompt.' -ForegroundColor DarkYellow
}
Write-Host ''
Write-StatusLine -Label 'XRCE' -State (Get-LaunchState -Needed $xrceNeeded -Opened ([bool]$xrceOpened))
Write-StatusLine -Label 'fc_telemetry' -State (Get-LaunchState -Needed $needTelemetry -Opened ([bool]$telemetryOpened))
Write-StatusLine -Label 'obstacles' -State (Get-LaunchState -Needed $needObstacles -Opened ([bool]$obstaclesOpened))
Write-StatusLine -Label 'MAVLink' -State 'waiting for PX4'
Write-Host 'Connect QGroundControl to UDP port 14550.'
Write-Host ''
Write-Host '--------'

if (-not $px4Running) {
    $command = "export PX4_HOME_LAT=$($Site.Lat); export PX4_HOME_LON=$($Site.Lon); export PX4_HOME_ALT=$($Site.Alt); cd ~/PX4-Autopilot && make px4_sitl gz_standard_vtol"
    & wsl.exe -d Ubuntu-24.04 -e bash -lc $command
    $sitlCode = $LASTEXITCODE
    if ($sitlCode -ne 0) {
        if (-not $mavProcess.HasExited) {
            Stop-Process -Id $mavProcess.Id -ErrorAction SilentlyContinue
        }
    }
}
else {
    $sitlCode = 0
}

$mavProcess.WaitForExit()
$mavFailed = $mavProcess.ExitCode -ne 0
Write-Host "MAVLink setup finished with exit code $($mavProcess.ExitCode). Log: /tmp/aeac-sitl-mavlink.log"
if (-not $px4Running) {
    exit $sitlCode
}
if ($mavFailed) {
    exit 1
}
exit 0
