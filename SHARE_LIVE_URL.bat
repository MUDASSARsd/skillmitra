@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   SkillMitra - Generate Public Live URL for PPT / Jury
echo ========================================================
echo.

rem Check if local server is running on port 8000
powershell -Command "$c = Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue; if ($c) { exit 0 } else { exit 1 }" >nul 2>nul
if errorlevel 1 (
    echo [!] Server is not running. Starting backend on port 8000 first...
    call "%~dp0_USE_PROJECT_PYTHON.bat"
    start "SkillMitra Backend" /min "%PYTHON_EXE%" -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
    timeout /t 3 /nobreak >nul
)

echo Starting Cloudflare Secure Tunnel...
echo Look for the line below that says:
echo   https://xxxxxx.trycloudflare.com
echo.
echo That is your live public link! Add /app to the end for the UI.
echo Press Ctrl+C when you want to stop sharing.
echo.
"%~dp0cloudflared.exe" tunnel --url http://127.0.0.1:8000
pause
