# ==============================================================================
# RetroVault Universal Windows Backup Agent - Service Uninstaller Script
# ==============================================================================
[CmdletBinding()]
param ()

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   RetroVault Backup Agent - Windows Service Uninstaller  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Require Administrator Privileges
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Administrator privileges are required to uninstall Windows Services. Please run PowerShell as Administrator."
    exit 1
}

$ServiceName = "RetroVaultAgent"
$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue

if (-not $existingService) {
    Write-Host "[*] Service $ServiceName is not installed." -ForegroundColor Yellow
    exit 0
}

Write-Host "[+] Stopping service $ServiceName..." -ForegroundColor Yellow
Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

Write-Host "[+] Removing service $ServiceName..." -ForegroundColor Cyan
sc.exe delete $ServiceName | Out-Null

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "   Service $ServiceName has been uninstalled successfully." -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
