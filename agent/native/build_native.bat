@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo RetroVault Native Windows Module Build Script (x64)
echo =======================================================

where cmake >nul 2>nul
if %errorlevel% neq 0 (
    if exist "C:\Program Files\CMake\bin\cmake.exe" (
        set "PATH=C:\Program Files\CMake\bin;!PATH!"
    ) else (
        echo [ERROR] CMake not found. Please install CMake or add it to PATH.
        exit /b 1
    )
)

set "SCRIPT_DIR=%~dp0"
set "BUILD_DIR=%SCRIPT_DIR%build"
set "BIN_DIR=%SCRIPT_DIR%bin"

if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
if not exist "%BIN_DIR%" mkdir "%BIN_DIR%"

echo Configuring CMake for Release x64...
cmake -B "%BUILD_DIR%" -S "%SCRIPT_DIR%"
if %errorlevel% neq 0 (
    echo [ERROR] CMake configuration failed.
    exit /b 1
)

echo Building native library...
cmake --build "%BUILD_DIR%" --config Release
if %errorlevel% neq 0 (
    echo [ERROR] Build failed.
    exit /b 1
)

if exist "%BIN_DIR%\libretrovault_native.dll" (
    copy /y "%BIN_DIR%\libretrovault_native.dll" "%BIN_DIR%\retrovault_native.dll" >nul
)

echo [SUCCESS] retrovault_native.dll built and verified in %BIN_DIR%
exit /b 0
