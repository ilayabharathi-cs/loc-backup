@echo off
setlocal enabledelayedexpansion
title RetroVault - Trigger Backup Now

echo =====================================================================
echo              RetroVault - Immediate Backup Runner
echo =====================================================================
echo.

cd /d "%~dp0"

:: Detect Python
set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else if exist "..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=..\.venv\Scripts\python.exe"
) else (
    set "PYTHON_EXE=python"
)

echo [*] Starting Immediate Full Backup to server...
echo.

for %%I in ("%~dp0..") do set "PARENT_DIR=%%~fI"
set "PYTHONPATH=%PARENT_DIR%;%~dp0;%PYTHONPATH%"

%PYTHON_EXE% src\main.py --backup-now

echo.
echo =====================================================================
echo Backup run finished. Check results above.
echo =====================================================================
pause
