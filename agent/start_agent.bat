@echo off
setlocal enabledelayedexpansion
title RetroVault Universal Windows Client Agent

echo =====================================================================
echo           RetroVault Universal Windows Backup Agent
echo =====================================================================
echo.

:: 1. Universal Root Directory Resolution (Relative to this batch file)
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"

:: Check if script is running from repository root or inside 'agent' folder
if exist "%APP_DIR%\agent\src\main.py" (
    set "AGENT_ROOT=%APP_DIR%\agent"
    set "MAIN_PY=%APP_DIR%\agent\src\main.py"
    set "REQ_TXT=%APP_DIR%\agent\requirements.txt"
) else if exist "%APP_DIR%\src\main.py" (
    set "AGENT_ROOT=%APP_DIR%"
    set "MAIN_PY=%APP_DIR%\src\main.py"
    set "REQ_TXT=%APP_DIR%\requirements.txt"
) else (
    echo [ERROR] Cannot locate agent\src\main.py!
    echo Please make sure this script is in the agent directory.
    pause
    exit /b 1
)

:: 2. Universal Python Detection (Venv -> Local Venv -> PATH -> Py Launcher)
set "PYTHON_EXE="

if exist "%APP_DIR%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%APP_DIR%\.venv\Scripts\python.exe"
) else if exist "%AGENT_ROOT%\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%AGENT_ROOT%\.venv\Scripts\python.exe"
) else (
    :: Check standard system python in PATH
    for %%P in (python.exe) do (
        set "FOUND=%%~$PATH:P"
        if defined FOUND set "PYTHON_EXE=python"
    )
    :: Fallback to Windows 'py' launcher
    if not defined PYTHON_EXE (
        for %%P in (py.exe) do (
            set "FOUND=%%~$PATH:P"
            if defined FOUND set "PYTHON_EXE=py -3"
        )
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] Python 3.10+ was not found on this computer!
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check 'Add Python to PATH' during installation.
    pause
    exit /b 1
)

echo [OK] Python detected: %PYTHON_EXE%

:: 3. Universal ProgramData / Configuration Resolution
if defined ProgramData (
    set "BASE_DATA=%ProgramData%"
) else if defined ALLUSERSPROFILE (
    set "BASE_DATA=%ALLUSERSPROFILE%"
) else (
    set "BASE_DATA=%LOCALAPPDATA%"
)

set "CONFIG_DIR=%BASE_DATA%\RetroVault\agent"
set "CONFIG_FILE=%CONFIG_DIR%\config.json"

if not exist "%CONFIG_DIR%" (
    mkdir "%CONFIG_DIR%" >nul 2>&1
)

:: 4. Auto-Install Dependencies if pydantic is missing
%PYTHON_EXE% -c "import pydantic" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo.
    echo [*] Installing required dependencies on this machine...
    %PYTHON_EXE% -m pip install -r "%REQ_TXT%"
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

:: 5. Server URL Configuration (Zero-Touch Deployment Support)
:: If config.json is bundled in agent folder, use it automatically with ZERO prompts
if exist "%AGENT_ROOT%\config.json" (
    echo [OK] Pre-configured agent package detected: %AGENT_ROOT%\config.json
    copy /y "%AGENT_ROOT%\config.json" "%CONFIG_FILE%" >nul 2>&1
    goto START_AGENT
)

if exist "%CONFIG_FILE%" (
    echo [OK] Existing configuration found: %CONFIG_FILE%
    goto START_AGENT
)

:PROMPT_IP
echo.
echo =====================================================================
echo                    Server Configuration
echo =====================================================================
echo Please enter the IP or hostname of your Linux Backup Server.
set /p SERVER_IP="Linux Server IP or hostname (e.g. 192.168.1.50): "

if "%SERVER_IP%"=="" (
    echo [ERROR] Server IP cannot be empty!
    goto PROMPT_IP
)

:: Write config.json dynamically
(
echo {
echo   "server_url": "http://%SERVER_IP%:8000",
echo   "heartbeat_interval_seconds": 30,
echo   "log_level": "INFO",
echo   "agent_version": "1.0.0"
echo }
) > "%CONFIG_FILE%"

echo.
echo [OK] Configuration saved: http://%SERVER_IP%:8000

:START_AGENT
echo.
echo ---------------------------------------------------------------------
echo Testing connection to Linux Backup Server...
echo ---------------------------------------------------------------------

cd /d "%APP_DIR%"

%PYTHON_EXE% -c "import urllib.request, json, sys; cfg=json.load(open(r'%CONFIG_FILE%')); res=urllib.request.urlopen(cfg['server_url']+'/health', timeout=5); sys.stdout.write('[OK] Connected! Server status: ' + res.read().decode() + '\n'); sys.exit(0)"
if !ERRORLEVEL! neq 0 (
    echo.
    echo [WARNING] Could not reach the server right now.
    echo Please verify:
    echo  1. The server is running (port 8000)
    echo  2. Firewall allows port 8000 on the host machine
    echo.
    echo Starting agent anyway and retrying in background...
)

echo.
echo =====================================================================
echo Connected! Starting RetroVault Universal Agent...
echo Automatic registration, device identity, and heartbeats are active.
echo Press Ctrl+C anytime in this window to stop.
echo =====================================================================
echo.

for %%I in ("%AGENT_ROOT%\..") do set "PARENT_DIR=%%~fI"
set "PYTHONPATH=%PARENT_DIR%;%AGENT_ROOT%;%PYTHONPATH%"

%PYTHON_EXE% "%MAIN_PY%" --run

:END
