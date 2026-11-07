@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"
title Campus Agent Demo Setup

echo ============================================================
echo   Campus Agent - one click demo reset
echo ============================================================
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please ask a technical teammate.
    pause
    exit /b 1
)

echo [1/4] Closing old demo server...
taskkill /F /T /FI "WINDOWTITLE eq Campus Agent Server*" >nul 2>&1
powershell -NoProfile -Command "$pids = netstat -ano | Select-String ':8000|:8011' | Where-Object { $_ -match 'LISTENING' } | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique; foreach ($p in $pids) { if ($p -match '^\d+$' -and $p -ne '0') { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue } }"
powershell -NoProfile -Command "Start-Sleep -Seconds 2"

echo [2/4] Clearing old demo data...
if exist data rmdir /s /q data >nul 2>&1
powershell -NoProfile -Command "Start-Sleep -Seconds 1"
if exist data rmdir /s /q data >nul 2>&1
if exist data (
    echo.
    echo [ERROR] Cannot clear data. Close the black server window and try again.
    pause
    exit /b 1
)

echo [3/4] Starting server...
start "Campus Agent Server" cmd /k "title Campus Agent Server & python -m uvicorn app.main:app --host 127.0.0.1 --port 8011"
echo Waiting for server to be ready...
powershell -NoProfile -Command "$ok=$false; for($i=0;$i -lt 30;$i++){ try { $h=Invoke-RestMethod 'http://127.0.0.1:8011/api/v1/health' -TimeoutSec 1; if($h.status -eq 'ok'){ $ok=$true; break } } catch {}; Start-Sleep -Milliseconds 500 }; if(-not $ok){ exit 1 }"
if errorlevel 1 (
    echo.
    echo [ERROR] Server did not start. Close old black windows and try again.
    pause
    exit /b 1
)

echo [4/4] Creating demo data...
set CAMPUS_BASE_URL=http://127.0.0.1:8011/api/v1
python scripts\seed_demo.py
if errorlevel 1 (
    echo.
    echo [ERROR] Demo data failed. Please ask a technical teammate.
    pause
    exit /b 1
)

start "" http://127.0.0.1:8011
echo.
echo Done. The browser should open automatically.
echo Keep the black window titled "Campus Agent Server" open.
echo.
powershell -NoProfile -Command "Start-Sleep -Seconds 5"
exit /b 0
