$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run this script from an Administrator PowerShell window.'
}

$ErrorActionPreference = 'Stop'

# This script checks for each prerequisite before installing it with winget.
# It also enables WSL without a distribution, configures resource limits when
# no user WSL configuration exists, and reports what changed and reboot needs.

$summary = [System.Collections.Generic.List[string]]::new()
$rebootNeeded = $false

if (-not (Get-Command winget.exe -ErrorAction SilentlyContinue)) {
    throw 'winget was not found. Install or update App Installer, then run this script again.'
}

function Test-WingetPackage {
    param([Parameter(Mandatory = $true)][string]$Id)

    $result = & winget.exe list --id $Id --exact --accept-source-agreements 2>&1
    return (($result | Out-String) -match [regex]::Escape($Id))
}

function Install-IfMissing {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Id
    )

    if (Test-WingetPackage -Id $Id) {
        $summary.Add("${Name}: already installed")
        return
    }

    Write-Host "Installing $Name..."
    & winget.exe install --id $Id --exact --accept-package-agreements --accept-source-agreements --silent
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -and $exitCode -ne 3010 -and $exitCode -ne 1641) {
        throw "winget failed to install $Name (exit code $exitCode)."
    }
    if ($exitCode -eq 3010 -or $exitCode -eq 1641) {
        $script:rebootNeeded = $true
    }
    $summary.Add("${Name}: installed")
}

Install-IfMissing -Name 'Git' -Id 'Git.Git'
Install-IfMissing -Name 'Node.js LTS' -Id 'OpenJS.NodeJS.LTS'
Install-IfMissing -Name 'Python 3.12' -Id 'Python.Python.3.12'
Install-IfMissing -Name 'Docker Desktop' -Id 'Docker.DockerDesktop'
Install-IfMissing -Name 'Ollama' -Id 'Ollama.Ollama'

$wslCommand = Get-Command wsl.exe -ErrorAction SilentlyContinue
if (-not $wslCommand) {
    throw 'wsl.exe was not found. Update Windows 11 and make sure the WSL feature is available, then run this script again.'
}
$wslReady = $false
& wsl.exe --status 2>$null | Out-Null
$wslReady = ($LASTEXITCODE -eq 0)

if ($wslReady) {
    $summary.Add('WSL: already installed')
} else {
    Write-Host 'Installing WSL without a Linux distribution...'
    & wsl.exe --install --no-distribution
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -and $exitCode -ne 3010 -and $exitCode -ne 1641) {
        throw "WSL installation failed (exit code $exitCode)."
    }
    $rebootNeeded = $true
    $summary.Add('WSL: installation requested')
}

$wslConfigPath = Join-Path $env:USERPROFILE '.wslconfig'
if (Test-Path -LiteralPath $wslConfigPath) {
    $summary.Add('WSL resource limits: existing .wslconfig preserved')
} else {
    @'
[wsl2]
memory=6GB
processors=4
'@ | Set-Content -LiteralPath $wslConfigPath -Encoding ascii
    $summary.Add('WSL resource limits: created .wslconfig (memory=6GB, processors=4)')
}

Write-Host "`nSetup summary:"
foreach ($item in $summary) {
    Write-Host " - $item"
}
if ($rebootNeeded) {
    Write-Host "`nReboot needed: Yes. Restart Windows before continuing."
} else {
    Write-Host "`nReboot needed: No."
}
