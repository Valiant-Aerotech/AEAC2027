# Shared WSL distro detection (fixes UTF-16 output from wsl -l on Windows).

function Get-ValiantRepoRoot {
    param([string]$FromScriptRoot = "")
    if ($FromScriptRoot) {
        return (Resolve-Path -LiteralPath (Join-Path $FromScriptRoot "..")).Path
    }
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "..")).Path
}

function Get-ValiantRepoPath {
    param(
        [Parameter(Mandatory = $true)][string]$RelativePath,
        [string]$FromScriptRoot = ""
    )
    $repo = Get-ValiantRepoRoot -FromScriptRoot $FromScriptRoot
    $rel = $RelativePath -replace '/', '\'
    if ($rel -like 'tools\*') {
        return (Join-Path $repo $rel)
    }
    return (Join-Path $repo (Join-Path "tools" $rel))
}

function ConvertTo-ValiantWslPath {
    param([Parameter(Mandatory = $true)][string]$WinPath)
    if (-not (Test-Path -LiteralPath $WinPath)) {
        throw "Cannot convert missing path to WSL: $WinPath"
    }
    $abs = (Resolve-Path -LiteralPath $WinPath).Path -replace '\\', '/'
    if ($abs -match '^([A-Za-z]):/(.*)$') {
        $drive = $matches[1].ToLower()
        $rest = $matches[2]
        return "/mnt/$drive/$rest"
    }
    throw "Cannot convert path to WSL mount (expected drive letter path): $WinPath"
}

function Get-WslDistroNames {
    # wsl -l -q is plain names; strip null bytes if UTF-16 leaks through
    $raw = (wsl -l -q 2>&1 | Out-String) -replace "`0", ""
    $names = @()
    foreach ($line in ($raw -split "`r?`n")) {
        $name = $line.Trim()
        if ($name) { $names += $name }
    }
    return $names
}

function Get-ValiantWslDistro {
    param(
        [string[]]$Prefer = @("Ubuntu", "Ubuntu-24.04", "Ubuntu-22.04", "Ubuntu-20.04")
    )
    foreach ($candidate in $Prefer) {
        foreach ($installed in (Get-WslDistroNames)) {
            if ($installed -eq $candidate) {
                return $installed
            }
        }
    }
    foreach ($installed in (Get-WslDistroNames)) {
        if ($installed -like "Ubuntu*") {
            return $installed
        }
    }
    return $null
}

function Test-ValiantWslReady {
    try {
        wsl echo ok 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) { return $false }
        return ($null -ne (Get-ValiantWslDistro))
    }
    catch {
        return $false
    }
}

function Invoke-ValiantWsl {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$WslArgs,
        [string]$Distro = ""
    )
    if (-not $Distro) {
        $Distro = Get-ValiantWslDistro
    }
    if (-not $Distro) {
        throw "No Ubuntu WSL distro found. Run: wsl -l -v"
    }
    $allArgs = @('-d', $Distro, '--') + $WslArgs
    $lines = & wsl @allArgs 2>&1
    foreach ($line in @($lines)) {
        if ($line -is [System.Management.Automation.ErrorRecord]) {
            Write-Host $line.ToString()
        } else {
            Write-Host $line
        }
    }
    return [int]$LASTEXITCODE
}
