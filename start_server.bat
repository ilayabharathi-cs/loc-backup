@echo off
setlocal enabledelayedexpansion
title RetroVault Backup Server (Control Plane)

echo =====================================================================
echo            RetroVault Backup Server - Control Plane
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Detect Python
set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "server\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=server\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

:: 2. Show Active Network IPs so user knows what to configure on clients
echo Detecting Local Network IP Addresses for Client Agents...
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.IPAddress -notlike '169.254*' } | ForEach-Object { Write-Host '  [+] Host IP:' $_.IPAddress '('$_.InterfaceAlias')' -ForegroundColor Green }"
echo.
echo Client agents should point their server_url to one of the above IPs on port 8000
echo (e.g. http://192.168.46.180:8000)
echo.
echo ---------------------------------------------------------------------
echo Starting RetroVault Server on 0.0.0.0:8000...
echo ---------------------------------------------------------------------
echo.

%PYTHON_EXE% run_server.py

pause
