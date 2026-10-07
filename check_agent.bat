@echo off
setlocal enabledelayedexpansion
title RetroVault Agent Status Check

echo =====================================================================
echo           RetroVault Universal Client Agent - Status Check
echo =====================================================================
echo.

set "AGENT_RUNNING=0"
set "RUN_TYPE="
set "RUN_DETAILS="

:: Resolve Directories (works whether script is in project root or agent/ folder)
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

if exist "%SCRIPT_DIR%\agent\src\main.py" (
    set "PROJECT_ROOT=%SCRIPT_DIR%"
    set "AGENT_DIR=%SCRIPT_DIR%\agent"
) else if exist "%SCRIPT_DIR%\src\main.py" (
    set "AGENT_DIR=%SCRIPT_DIR%"
    for %%I in ("%SCRIPT_DIR%\..") do set "PROJECT_ROOT=%%~fI"
) else (
    set "PROJECT_ROOT=%SCRIPT_DIR%"
    set "AGENT_DIR=%SCRIPT_DIR%\agent"
)

:: 1. Check Windows Service (RetroVaultAgent)
set "SERVICE_NAME=RetroVaultAgent"
sc query "%SERVICE_NAME%" >nul 2>&1
if !ERRORLEVEL! equ 0 (
    for /f "tokens=3 delims=: " %%H in ('sc query "%SERVICE_NAME%" ^| findstr /i "STATE"') do (
        set "SVC_STATE=%%H"
    )
    if /i "!SVC_STATE!"=="RUNNING" (
        set "AGENT_RUNNING=1"
        set "RUN_TYPE=Windows Service"
        set "RUN_DETAILS=%SERVICE_NAME% - Running"
        echo [OK] Windows Service detected: %SERVICE_NAME% is RUNNING.
    ) else (
        echo [INFO] Windows Service %SERVICE_NAME% is registered but state is !SVC_STATE!.
    )
) else (
    echo [INFO] Windows Service '%SERVICE_NAME%' is not registered.
)

:: 2. Check Running Process (Python or Compiled Agent Daemon)
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -match 'main\.py.*--run' -or $_.CommandLine -match 'agent[\\/]src[\\/]main\.py.*--run' -or ($_.Name -match 'RetroVaultAgent\.exe' -and $_.ProcessId -ne $PID)) -and $_.ProcessId -ne $PID };" ^
  "if ($procs) {" ^
  "  foreach ($p in $procs) {" ^
  "    Write-Host ('[OK] Process Active: PID ' + $p.ProcessId + ' - Name: ' + $p.Name) -ForegroundColor Green;" ^
  "    Write-Host ('     Command: ' + $p.CommandLine) -ForegroundColor Gray;" ^
  "  };" ^
  "  exit 0;" ^
  "} else { exit 1; }"

if !ERRORLEVEL! equ 0 (
    set "AGENT_RUNNING=1"
    if not defined RUN_TYPE (
        set "RUN_TYPE=Background Process"
        set "RUN_DETAILS=Agent Python Process Active"
    )
)

echo.
echo ---------------------------------------------------------------------
echo Configuration and Identity Details:
echo ---------------------------------------------------------------------

:: 3. Check Configuration File
set "FOUND_CONFIG="
if defined ProgramData (
    if exist "%ProgramData%\RetroVault\agent\config.json" set "FOUND_CONFIG=%ProgramData%\RetroVault\agent\config.json"
)
if not defined FOUND_CONFIG if exist "%AGENT_DIR%\config.json" set "FOUND_CONFIG=%AGENT_DIR%\config.json"
if not defined FOUND_CONFIG if exist "%PROJECT_ROOT%\config.json" set "FOUND_CONFIG=%PROJECT_ROOT%\config.json"

if defined FOUND_CONFIG (
    echo   [+] Config File: %FOUND_CONFIG%
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$cfg = Get-Content -Raw -Path '%FOUND_CONFIG%' | ConvertFrom-Json;" ^
      "Write-Host ('      Server URL: ' + $cfg.server_url);" ^
      "Write-Host ('      Heartbeat Interval: ' + $cfg.heartbeat_interval_seconds + 's');" ^
      "Write-Host ('      Agent Version: ' + $cfg.agent_version);"
) else (
    echo   [-] Config File: Not found - default config will be generated on startup
)

:: 4. Check Identity File
set "FOUND_IDENTITY="
if defined ProgramData (
    if exist "%ProgramData%\RetroVault\agent\identity.json" set "FOUND_IDENTITY=%ProgramData%\RetroVault\agent\identity.json"
)
if not defined FOUND_IDENTITY if exist "%AGENT_DIR%\identity.json" set "FOUND_IDENTITY=%AGENT_DIR%\identity.json"

if defined FOUND_IDENTITY (
    echo   [+] Identity File: %FOUND_IDENTITY%
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "$id = Get-Content -Raw -Path '%FOUND_IDENTITY%' | ConvertFrom-Json;" ^
      "Write-Host ('      Device ID: ' + $id.device_id);" ^
      "if ($id.client_id) { Write-Host ('      Client ID: ' + $id.client_id + ' [Enrolled]') -ForegroundColor Green } else { Write-Host '      Client ID: Not Enrolled Yet' -ForegroundColor Yellow };"
) else (
    echo   [-] Identity File: Not created yet - will be created on first run
)

:: 5. Check Log File
set "FOUND_LOG="
if defined ProgramData (
    if exist "%ProgramData%\RetroVault\agent\logs\agent.log" set "FOUND_LOG=%ProgramData%\RetroVault\agent\logs\agent.log"
)
if not defined FOUND_LOG if exist "%AGENT_DIR%\logs\agent.log" set "FOUND_LOG=%AGENT_DIR%\logs\agent.log"

if defined FOUND_LOG (
    echo.
    echo ---------------------------------------------------------------------
    echo Recent Agent Logs:
    echo ---------------------------------------------------------------------
    powershell -NoProfile -ExecutionPolicy Bypass -Command ^
      "Get-Content -Path '%FOUND_LOG%' -Tail 5 | ForEach-Object { Write-Host ('  ' + $_) -ForegroundColor Gray }"
)

echo.
echo =====================================================================
if "!AGENT_RUNNING!"=="1" (
    echo [RUNNING] RetroVault Agent is ACTIVE and RUNNING!
    echo Type: !RUN_TYPE! - !RUN_DETAILS!
    echo =====================================================================
    echo.
    set "EXIT_CODE=0"
) else (
    echo [STOPPED] RetroVault Agent is NOT running.
    echo.
    echo To start the agent:
    echo   - Foreground: run start_agent.bat
    echo   - As Windows Service: powershell agent\scripts\install_service.ps1
    echo =====================================================================
    echo.
    set "EXIT_CODE=1"
)

:: Pause only if user double-clicked script from Windows Explorer without bypass flag
if /i "%1"=="--no-pause" goto SKIP_PAUSE
if /i "%1"=="-n" goto SKIP_PAUSE
echo %cmdcmdline% | findstr /i /c:"%~nx0" >nul 2>&1
if !ERRORLEVEL! equ 0 (
    pause
)
:SKIP_PAUSE

exit /b !EXIT_CODE!

