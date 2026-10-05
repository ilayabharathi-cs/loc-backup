@echo off
REM ==============================================================================
REM  RetroVault Agent - 1-Click Windows LAN Installer & Service Register
REM ==============================================================================
REM Usage:
REM   install_agent.bat [LINUX_SERVER_IP_OR_HOSTNAME]
REM Example:
REM   install_agent.bat 192.168.1.50
REM ==============================================================================

setlocal enabledelayedexpansion

set SERVER_HOST=%1
if "%SERVER_HOST%"=="" (
    set SERVER_HOST=192.168.1.100
)

REM Require Administrator Privileges
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [ERROR] This installer requires Administrator privileges.
    echo Please right-click install_agent.bat and select "Run as administrator".
    pause
    exit /b 1
)

set INSTALL_DIR=C:\Program Files\RetroVault
set DATA_DIR=C:\ProgramData\RetroVault\agent
set LOG_DIR=%DATA_DIR%\logs
set SCRIPT_DIR=%~dp0

echo ==============================================================
echo   RetroVault Backup Agent - Windows LAN Service Deployment
echo ==============================================================
echo [INFO] Target Linux Server: http://%SERVER_HOST%:8000
echo [INFO] Destination Folder:  %INSTALL_DIR%
echo.

REM 1. Create target directories
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%DATA_DIR%" mkdir "%DATA_DIR%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

REM 2. Copy Executable
if exist "%SCRIPT_DIR%RetroVaultAgent.exe" (
    copy /y "%SCRIPT_DIR%RetroVaultAgent.exe" "%INSTALL_DIR%\RetroVaultAgent.exe" >nul
) else if exist "%SCRIPT_DIR%..\dist\RetroVaultAgent.exe" (
    copy /y "%SCRIPT_DIR%..\dist\RetroVaultAgent.exe" "%INSTALL_DIR%\RetroVaultAgent.exe" >nul
) else if exist "RetroVaultAgent.exe" (
    copy /y "RetroVaultAgent.exe" "%INSTALL_DIR%\RetroVaultAgent.exe" >nul
) else (
    echo [ERROR] RetroVaultAgent.exe not found!
    echo Place RetroVaultAgent.exe in the same folder as this script.
    pause
    exit /b 1
)

echo [+] Executable installed to: %INSTALL_DIR%\RetroVaultAgent.exe

REM 3. Generate LAN config.json
set CONFIG_FILE=%DATA_DIR%\config.json
(
    echo {
    echo   "server_url": "http://%SERVER_HOST%:8000",
    echo   "heartbeat_interval_seconds": 30,
    echo   "log_level": "INFO",
    echo   "request_timeout_seconds": 15,
    echo   "max_retries": 5,
    echo   "verify_ssl": false,
    echo   "agent_version": "1.0.0"
    echo }
) > "%CONFIG_FILE%"

echo [+] Configuration written to: %CONFIG_FILE%

REM 4. Stop and Remove Old Service if it exists
sc.exe query RetroVaultAgent >nul 2>&1
if %errorLevel% equ 0 (
    echo [*] Stopping previous RetroVaultAgent service...
    sc.exe stop RetroVaultAgent >nul 2>&1
    timeout /t 2 /nobreak >nul
    sc.exe delete RetroVaultAgent >nul 2>&1
    timeout /t 1 /nobreak >nul
)

REM 5. Register New Windows Service
echo [+] Registering RetroVaultAgent as Windows Service...
sc.exe create RetroVaultAgent binPath= "\"%INSTALL_DIR%\RetroVaultAgent.exe\" --run" start= auto DisplayName= "RetroVault Backup Agent" >nul
sc.exe description RetroVaultAgent "Automated enterprise backup client reporting to Linux control plane." >nul

REM 6. Configure Service Failure Auto-Restart
sc.exe failure RetroVaultAgent reset= 86400 actions= restart/5000/restart/10000/restart/30000 >nul

REM 7. Start the Service
echo [+] Starting RetroVaultAgent service...
sc.exe start RetroVaultAgent >nul

echo.
echo ==============================================================
echo   SUCCESS: RetroVault Agent Installed and Running!
echo ==============================================================
echo The agent will now:
echo   1. Self-register with Linux server at http://%SERVER_HOST%:8000
echo   2. Report system health (CPU, RAM, Disks, Users) every 30s
echo   3. Start automatically on Windows boot
echo.
pause
