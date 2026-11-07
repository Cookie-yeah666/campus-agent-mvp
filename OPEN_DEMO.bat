@echo off
chcp 65001 >nul
cd /d "%~dp0"

powershell -NoProfile -Command "if (netstat -ano | Select-String ':8011' | Where-Object { $_ -match 'LISTENING' }) { exit 0 } else { exit 1 }"
if errorlevel 1 (
    echo.
    echo The demo server is NOT running.
    echo Please double-click START_DEMO.bat first.
    echo.
    pause
    exit /b 1
)

start "" http://127.0.0.1:8011
exit /b 0
