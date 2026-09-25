@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"
call "%~dp0_USE_PROJECT_PYTHON.bat"

echo ========================================================
echo   SkillMitra - Offline Mobile Phone Demo (0 Internet)
echo ========================================================
echo.

rem Stop any server occupying port 8000
powershell -Command "$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; if ($conns) { $conns | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} } }" >nul 2>nul
timeout /t 1 /nobreak >nul

rem Detect local IP using Python
for /f "delims=" %%I in ('"%PYTHON_EXE%" -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); (lambda: (s.connect(('8.8.8.8', 80)), print(s.getsockname()[0]), s.close()))() if True else None" 2^>nul') do set "LOCAL_IP=%%I"
if "!LOCAL_IP!"=="" set "LOCAL_IP=192.168.29.239"

echo --------------------------------------------------------
echo  INSTRUCTIONS FOR 100%% OFFLINE PHONE DEMO:
echo --------------------------------------------------------
echo  1. Turn on Mobile Hotspot on your phone (or connect both
echo     phone and laptop to the same Wi-Fi router).
echo     *** MOBILE DATA / INTERNET CAN BE COMPLETELY OFF! ***
echo.
echo  2. On your phone's browser (Chrome / Safari), open:
echo.
echo     ====================================================
echo       http://!LOCAL_IP!:8000/app
echo     ====================================================
echo.
echo --------------------------------------------------------
echo Starting backend engine on 0.0.0.0:8000 ...
echo Press Ctrl+C to stop.
echo.

start http://127.0.0.1:8000/app
"%PYTHON_EXE%" -m uvicorn backend.api.app:app --host 0.0.0.0 --port 8000
pause
