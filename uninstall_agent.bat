@echo off
setlocal enabledelayedexpansion
title RetroVault Agent - Complete Client Uninstaller

echo =====================================================================
echo    RetroVault Universal Client Agent - Complete Removal ^& Cleanup
echo =====================================================================
echo.

:: 0. Check Parameters
set "FORCE=0"
set "NO_PAUSE=0"
for %%A in (%*) do (
    if /i "%%A"=="--force" set "FORCE=1"
    if /i "%%A"=="-f" set "FORCE=1"
    if /i "%%A"=="--no-pause" set "NO_PAUSE=1"
    if /i "%%A"=="-n" set "NO_PAUSE=1"
)

:: Confirm with user unless --force is given
if "!FORCE!"=="0" (
    echo WARNING: This will:
    echo   1. Kill all running agent background processes.
    echo   2. Stop and delete the Windows Service [RetroVaultAgent].
    echo   3. Remove automatic startup persistence from Registry and Startup folder.
    echo   4. Clean up all agent configuration, identities, logs, and cache.
    echo.
    set /p CONFIRM="Are you sure you want to proceed? (Y/n): "
    if /i "!CONFIRM!"=="n" (
        echo [INFO] Uninstallation aborted by user.
        goto END
    )
    if /i "!CONFIRM!"=="no" (
        echo [INFO] Uninstallation aborted by user.
        goto END
    )
)

echo.
echo =====================================================================
echo [*] Phase 1: Terminating all Agent Background Processes...
echo =====================================================================

:: Forcefully close any command windows running the agent
taskkill /F /FI "WINDOWTITLE eq RetroVault Universal Windows Client Agent*" >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq RetroVault - Immediate Backup Runner*" >nul 2>&1
taskkill /F /IM RetroVaultAgent.exe >nul 2>&1

:: Query and kill all Python agent processes using PowerShell
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$procs = Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -match 'main\.py.*--run' -or $_.CommandLine -match 'agent[\\/]src[\\/]main\.py' -or $_.CommandLine -match 'agent\.main' -or $_.Name -eq 'RetroVaultAgent.exe') -and $_.ProcessId -ne $PID };" ^
  "if ($procs) {" ^
  "  foreach ($p in $procs) {" ^
  "    Write-Host ('  [+] Terminating Process PID: ' + $p.ProcessId + ' (' + $p.Name + ')') -ForegroundColor Yellow;" ^
  "    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue;" ^
  "  };" ^
  "} else {" ^
  "  Write-Host '  [OK] No active agent background processes found.' -ForegroundColor Green;" ^
  "}"

:: Wait 1 second safely without timeout input redirection error
ping 127.0.0.1 -n 2 >nul

echo.
echo =====================================================================
echo [*] Phase 2: Stopping and Removing Windows Service...
echo =====================================================================

set "SERVICE_NAME=RetroVaultAgent"
sc query "%SERVICE_NAME%" >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo   [*] Service '%SERVICE_NAME%' detected. Stopping service...
    net stop "%SERVICE_NAME%" >nul 2>&1
    sc stop "%SERVICE_NAME%" >nul 2>&1
    ping 127.0.0.1 -n 3 >nul
    
    echo   [*] Deleting service '%SERVICE_NAME%'...
    sc delete "%SERVICE_NAME%" >nul 2>&1
    if !ERRORLEVEL! equ 0 (
        echo   [OK] Service '%SERVICE_NAME%' deleted successfully.
    ) else (
        echo   [WARNING] Could not delete service. Administrator privileges may be required.
        echo             Run CMD as Administrator if the service still appears in services.msc.
    )
) else (
    echo   [OK] Windows Service '%SERVICE_NAME%' is not installed.
)

echo.
echo =====================================================================
echo [*] Phase 3: Removing Windows Startup Persistence...
echo =====================================================================

:: 1. Remove Registry Key (Current User)
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "RetroVaultAgent" /f >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo   [OK] Removed RetroVaultAgent from HKCU Startup Registry.
) else (
    echo   [INFO] No HKCU Startup Registry entry found.
)

:: 2. Remove Registry Key (Local Machine - if run as Admin)
reg delete "HKLM\Software\Microsoft\Windows\CurrentVersion\Run" /v "RetroVaultAgent" /f >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo   [OK] Removed RetroVaultAgent from HKLM Startup Registry.
)

:: 3. Remove Startup Folder Scripts
if defined APPDATA (
    set "USER_STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
    if exist "!USER_STARTUP!\RetroVaultAgent.cmd" (
        del /f /q "!USER_STARTUP!\RetroVaultAgent.cmd" >nul 2>&1
        echo   [OK] Removed launcher script from User Startup folder.
    )
    if exist "!USER_STARTUP!\RetroVaultAgent.lnk" (
        del /f /q "!USER_STARTUP!\RetroVaultAgent.lnk" >nul 2>&1
        echo   [OK] Removed shortcut from User Startup folder.
    )
)

if defined ALLUSERSPROFILE (
    set "ALL_STARTUP=%ALLUSERSPROFILE%\Microsoft\Windows\Start Menu\Programs\Startup"
    if exist "!ALL_STARTUP!\RetroVaultAgent.cmd" (
        del /f /q "!ALL_STARTUP!\RetroVaultAgent.cmd" >nul 2>&1
        echo   [OK] Removed launcher script from All Users Startup folder.
    )
)

echo.
echo =====================================================================
echo [*] Phase 4: Cleaning Up Data, Configuration, Cache and Logs...
echo =====================================================================

:: 1. Clean ProgramData\RetroVault\agent
if defined ProgramData (
    if exist "%ProgramData%\RetroVault\agent" (
        echo   [*] Cleaning %ProgramData%\RetroVault\agent...
        rmdir /s /q "%ProgramData%\RetroVault\agent" >nul 2>&1
        if not exist "%ProgramData%\RetroVault\agent" (
            echo   [OK] Removed ProgramData agent directory.
        ) else (
            echo   [WARNING] Some files in ProgramData could not be removed (may need admin rights).
        )
    )
)

:: 2. Clean AppData\RetroVault\agent
if defined APPDATA (
    if exist "%APPDATA%\RetroVault\agent" (
        echo   [*] Cleaning %APPDATA%\RetroVault\agent...
        rmdir /s /q "%APPDATA%\RetroVault\agent" >nul 2>&1
        if not exist "%APPDATA%\RetroVault\agent" (
            echo   [OK] Removed AppData agent directory.
        )
    )
)

:: 3. Clean Local directory runtime artifacts (logs, identity)
set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

if exist "%SCRIPT_DIR%\agent\logs" rmdir /s /q "%SCRIPT_DIR%\agent\logs" >nul 2>&1
if exist "%SCRIPT_DIR%\logs" rmdir /s /q "%SCRIPT_DIR%\logs" >nul 2>&1
if exist "%SCRIPT_DIR%\agent\locks" rmdir /s /q "%SCRIPT_DIR%\agent\locks" >nul 2>&1
if exist "%SCRIPT_DIR%\locks" rmdir /s /q "%SCRIPT_DIR%\locks" >nul 2>&1

echo   [OK] Local runtime cache and logs cleaned.

echo.
echo =====================================================================
echo [*] Phase 5: Verification Check...
echo =====================================================================

set "CLEAN_SUCCESS=1"

:: Verify no processes remain
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$alive = Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -match 'main\.py.*--run' -or $_.CommandLine -match 'agent[\\/]src[\\/]main\.py' -or $_.Name -eq 'RetroVaultAgent.exe') -and $_.ProcessId -ne $PID };" ^
  "if ($alive) { exit 1 } else { exit 0 }"

if !ERRORLEVEL! neq 0 (
    echo   [WARNING] Some agent processes could not be killed.
    set "CLEAN_SUCCESS=0"
) else (
    echo   [OK] Zero agent processes running.
)

:: Verify service is gone
sc query "%SERVICE_NAME%" >nul 2>&1
if !ERRORLEVEL! equ 0 (
    echo   [WARNING] Windows Service %SERVICE_NAME% is still registered.
    set "CLEAN_SUCCESS=0"
) else (
    echo   [OK] Windows Service is completely removed.
)

echo.
echo =====================================================================
if "!CLEAN_SUCCESS!"=="1" (
    echo [SUCCESS] RetroVault Client Agent has been COMPLETELY REMOVED!
    echo   - All background processes killed
    echo   - Windows Service stopped and uninstalled
    echo   - Auto-startup persistence removed
    echo   - Config, identity, logs, and lock files cleared
) else (
    echo [COMPLETED WITH WARNINGS] Most items were removed, but please verify
    echo if Administrator privileges are needed for remaining service entries.
)
echo =====================================================================
echo.

:END
if "!NO_PAUSE!"=="0" (
    echo %cmdcmdline% | findstr /i /c:"%~nx0" >nul 2>&1
    if !ERRORLEVEL! equ 0 pause
)

exit /b 0
