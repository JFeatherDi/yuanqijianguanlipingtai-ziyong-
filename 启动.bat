@echo off
chcp 65001 >nul
rem IOTAT Components Platform - double-click to start (Windows)
rem Options: -Port 5001 / -NoBrowser / -Reinstall   (see 快速开始.md)
setlocal
cd /d "%~dp0"

set "PS1=%~dp0启动.ps1"
if not exist "%PS1%" set "PS1=%~dp0start.ps1"
if not exist "%PS1%" (
    echo [X] launcher .ps1 not found next to this .bat
    pause
    exit /b 1
)

where pwsh >nul 2>&1
if not errorlevel 1 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
    exit /b %errorlevel%
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%" %*
if errorlevel 1 (
    echo.
    echo [X] Launcher exited with an error. Run manually to see details:
    echo     powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
    pause
)
exit /b %errorlevel%
