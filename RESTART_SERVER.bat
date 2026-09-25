@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   Restarting SkillMitra / JeevikaMitra Server
echo ========================================================
echo.

echo Stopping existing server on port 8000...
powershell -Command "$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; if ($conns) { $conns | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host ('Stopped process on port 8000 (PID: ' + $_.OwningProcess + ')') } catch {} } }"
timeout /t 2 /nobreak >nul

echo Starting fresh server...
call "%~dp0START_HYBRID.bat"
