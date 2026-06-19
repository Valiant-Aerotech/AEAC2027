# Shared WSL distro detection (fixes UTF-16 output from wsl -l on Windows).

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
        [string[]]$WslArgs
    )
    $distro = Get-ValiantWslDistro
    if (-not $distro) {
        throw "No Ubuntu WSL distro found. Run: wsl -l -v"
    }
    & wsl -d $distro @WslArgs
    return $LASTEXITCODE
}
