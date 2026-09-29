@echo off
setlocal enabledelayedexpansion
title RetroVault Server & Dashboard Launcher

echo =====================================================================
echo         RetroVault - Complete Server & Dashboard Launcher
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Detect Python Virtual Environment
set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "server\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=server\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

:: 2. Display Server Network IPs
echo Detecting Server IP Addresses for Client Agents...
powershell -NoProfile -Command "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike '*Loopback*' -and $_.IPAddress -notlike '169.254*' } | ForEach-Object { Write-Host '  [+] Local IP:' $_.IPAddress '('$_.InterfaceAlias')' -ForegroundColor Green }"
echo.
echo Client agents should connect to: http://192.168.46.180:8000
echo.

:: 3. Launch Backend API Server (Port 8000)
echo [*] Starting Backend API Server (Port 8000)...
start "RetroVault Backend Server (Port 8000)" cmd /k "title RetroVault Backend Server (Port 8000) && %PYTHON_EXE% run_server.py"

:: 4. Launch Frontend Web UI (Port 5173)
echo [*] Starting Web UI Dashboard (Port 5173)...
start "RetroVault Web Dashboard (Port 5173)" cmd /k "title RetroVault Web Dashboard (Port 5173) && npm run dev"

:: 5. Wait a moment and launch Browser
echo.
echo [*] Waiting 3 seconds for services to boot...
timeout /t 3 /nobreak >nul

echo [*] Opening RetroVault Web Dashboard in browser...
start http://localhost:5173

echo.
echo =====================================================================
echo [SUCCESS] Both Backend Server and Frontend Dashboard are RUNNING!
echo.
echo  - Backend API:    http://0.0.0.0:8000 (Health: http://localhost:8000/health)
echo  - Web Dashboard:  http://localhost:5173
echo.
echo You can minimize this window.
echo To stop everything later, just close the two opened console windows.
echo =====================================================================
pause
