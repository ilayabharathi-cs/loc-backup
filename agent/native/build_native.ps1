# RetroVault Native Windows Module Build Script (PowerShell x64)
$ErrorActionPreference = "Stop"

Write-Host "======================================================="
Write-Host "RetroVault Native Windows Module Build Script (x64)"
Write-Host "======================================================="

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $scriptDir "build"
$binDir = Join-Path $scriptDir "bin"

New-Item -ItemType Directory -Force -Path $buildDir, $binDir | Out-Null

# Detect LLVM / MinGW or MSVC if needed
$toolBin = "C:\Users\ilaya\AppData\Local\Microsoft\WinGet\Packages\MartinStorsjo.LLVM-MinGW.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\llvm-mingw-20260616-ucrt-x86_64\bin"
if (Test-Path $toolBin) {
    $env:Path = "$toolBin;$env:Path"
}
if (Test-Path "C:\Program Files\CMake\bin") {
    $env:Path = "C:\Program Files\CMake\bin;$env:Path"
}

Write-Host "Configuring CMake..."
& cmake -B $buildDir -S $scriptDir

Write-Host "Building Release binary..."
& cmake --build $buildDir --config Release

$builtDll = Join-Path $binDir "libretrovault_native.dll"
$targetDll = Join-Path $binDir "retrovault_native.dll"
if (Test-Path $builtDll) {
    Copy-Item $builtDll $targetDll -Force
}

if (Test-Path $targetDll) {
    Write-Host "[SUCCESS] retrovault_native.dll built and verified at: $targetDll"
} else {
    Write-Error "Build completed but target DLL not found."
}
