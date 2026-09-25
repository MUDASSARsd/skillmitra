@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   Stopping SkillMitra / JeevikaMitra Server (Port 8000)
echo ========================================================
echo.

powershell -Command "$conns = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue; if ($conns) { $conns | ForEach-Object { try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host ('Stopped process on port 8000 (PID: ' + $_.OwningProcess + ')') } catch {} } } else { Write-Host 'No server was running on port 8000.' }"

echo.
echo Port 8000 is now free.
pause
