@echo off
setlocal
cd /d "%~dp0"
call "%~dp0_USE_PROJECT_PYTHON.bat"

echo ========================================================
echo   SkillMitra - PM-AJAY Livelihood Assistant (Desktop App)
echo ========================================================
echo.

rem Check if port 8000 is already active
powershell -Command "$c = Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue; if ($c) { exit 0 } else { exit 1 }" >nul 2>nul
if errorlevel 1 (
    echo [1/2] Starting SkillMitra backend engine...
    start "SkillMitra Backend" /min "%PYTHON_EXE%" -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
    timeout /t 3 /nobreak >nul
) else (
    echo [1/2] SkillMitra backend is already running on port 8000.
)

echo [2/2] Opening SkillMitra Native App window...
set "EDGE_X86=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
set "EDGE_X64=C:\Program Files\Microsoft\Edge\Application\msedge.exe"
set "CHROME=C:\Program Files\Google\Chrome\Application\chrome.exe"
set "CHROME_X86=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

if exist "%EDGE_X86%" (
    start "" "%EDGE_X86%" --app=http://127.0.0.1:8000/app --window-size=1280,850
) else if exist "%EDGE_X64%" (
    start "" "%EDGE_X64%" --app=http://127.0.0.1:8000/app --window-size=1280,850
) else if exist "%CHROME%" (
    start "" "%CHROME%" --app=http://127.0.0.1:8000/app --window-size=1280,850
) else if exist "%CHROME_X86%" (
    start "" "%CHROME_X86%" --app=http://127.0.0.1:8000/app --window-size=1280,850
) else (
    start http://127.0.0.1:8000/app
)

echo.
echo SkillMitra App is active.
