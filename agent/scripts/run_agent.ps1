# ==============================================================================
# RetroVault Universal Windows Backup Agent - Development / Standalone Runner
# ==============================================================================
[CmdletBinding()]
param (
    [string]$Config = "",
    [switch]$Register,
    [switch]$HeartbeatOnce,
    [switch]$SysInfo,
    [switch]$ResolvePolicy
)

$InstallDir = (Get-Item $PSScriptRoot).Parent.FullName
$VenvPython = Join-Path (Get-Item $InstallDir).Parent.FullName "server\.venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
} else {
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
}

$MainScript = Join-Path $InstallDir "src\main.py"

$ArgsList = @()
if (-not [string]::IsNullOrWhiteSpace($Config)) {
    $ArgsList += "--config", "`"$Config`""
}

if ($Register) {
    $ArgsList += "--register"
} elseif ($HeartbeatOnce) {
    $ArgsList += "--heartbeat-once"
} elseif ($SysInfo) {
    $ArgsList += "--sysinfo"
} elseif ($ResolvePolicy) {
    $ArgsList += "--resolve-policy"
} else {
    $ArgsList += "--run"
}

Write-Host "Running RetroVault Backup Agent: $PythonExe $MainScript $($ArgsList -join ' ')" -ForegroundColor Cyan
& $PythonExe $MainScript @ArgsList
