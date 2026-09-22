# ==============================================================================
# RetroVault Universal Windows Backup Agent - Service Installation Script
# ==============================================================================
[CmdletBinding()]
param (
    [string]$ServerUrl = "http://127.0.0.1:8000",
    [string]$PythonExe = "",
    [string]$InstallDir = ""
)

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   RetroVault Backup Agent - Windows Service Installer    " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Require Administrator Privileges
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Administrator privileges are required to install Windows Services. Please run PowerShell as Administrator."
    exit 1
}

# 2. Determine Paths
$ProgramDataDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::CommonApplicationData)
$AgentDataDir = Join-Path $ProgramDataDir "RetroVault\agent"
$AgentLogDir = Join-Path $AgentDataDir "logs"
$ConfigFile = Join-Path $AgentDataDir "config.json"

if (-not (Test-Path $AgentDataDir)) {
    New-Item -ItemType Directory -Path $AgentDataDir -Force | Out-Null
    Write-Host "[+] Created data directory: $AgentDataDir" -ForegroundColor Green
}
if (-not (Test-Path $AgentLogDir)) {
    New-Item -ItemType Directory -Path $AgentLogDir -Force | Out-Null
    Write-Host "[+] Created log directory: $AgentLogDir" -ForegroundColor Green
}

# 3. Create or Update Default Configuration
if (-not (Test-Path $ConfigFile)) {
    $defaultConfig = @"
{
  "server_url": "$ServerUrl",
  "heartbeat_interval_seconds": 30,
  "log_level": "INFO",
  "request_timeout_seconds": 10,
  "max_retries": 5,
  "verify_ssl": true,
  "agent_version": "1.0.0"
}
"@
    Set-Content -Path $ConfigFile -Value $defaultConfig -Encoding UTF8
    Write-Host "[+] Created configuration: $ConfigFile" -ForegroundColor Green
} else {
    Write-Host "[*] Configuration already exists: $ConfigFile" -ForegroundColor Yellow
}

# 4. Determine Python Executable and Agent Script
if ([string]::IsNullOrWhiteSpace($InstallDir)) {
    $InstallDir = (Get-Item $PSScriptRoot).Parent.FullName
}
$AgentScript = Join-Path $InstallDir "src\main.py"

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    # Check virtual environment or system Python
    $VenvPython = Join-Path (Get-Item $InstallDir).Parent.FullName "server\.venv\Scripts\python.exe"
    if (Test-Path $VenvPython) {
        $PythonExe = $VenvPython
    } else {
        $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
    }
}

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python executable could not be found. Please pass -PythonExe <path>."
    exit 1
}

Write-Host "[*] Using Python: $PythonExe" -ForegroundColor Cyan
Write-Host "[*] Using Agent:  $AgentScript" -ForegroundColor Cyan

# 5. Service Definition
$ServiceName = "RetroVaultAgent"
$DisplayName = "RetroVault Backup Agent"
$Description = "Continuous, enterprise-grade universal local backup agent for RetroVault."
$BinaryPath = "`"$PythonExe`" `"$AgentScript`" --run"

# Check if service already exists
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($existingService) {
    Write-Host "[*] Service $ServiceName is already registered. Stopping and updating..." -ForegroundColor Yellow
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    sc.exe delete $ServiceName | Out-Null
    Start-Sleep -Seconds 1
}

# 6. Create Windows Service
Write-Host "[+] Registering Windows Service: $ServiceName..." -ForegroundColor Cyan
New-Service -Name $ServiceName `
            -BinaryPathName $BinaryPath `
            -DisplayName $DisplayName `
            -Description $Description `
            -StartupType Automatic | Out-Null

# 7. Configure Failure Recovery Actions (Restart on crash)
sc.exe failure $ServiceName reset= 86400 actions= restart/5000/restart/10000/restart/30000 | Out-Null

# 8. Start Service
Write-Host "[+] Starting $ServiceName..." -ForegroundColor Green
Start-Service -Name $ServiceName

$status = (Get-Service -Name $ServiceName).Status
Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "   Service $ServiceName is now $status!                   " -ForegroundColor Green
Write-Host "   Logs: $AgentLogDir\agent.log                           " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
