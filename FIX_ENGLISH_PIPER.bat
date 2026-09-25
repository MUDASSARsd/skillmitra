@echo off
setlocal
cd /d "%~dp0"
call "%~dp0_USE_PROJECT_PYTHON.bat"

echo ================================================
echo SkillMitra - Fix Natural Offline English Voice
echo ================================================
echo.
"%PYTHON_EXE%" fix_english_piper.py
if errorlevel 1 (
  echo.
  echo FIX FAILED. Copy the error shown above.
  pause
  exit /b 1
)
echo.
echo FIX COMPLETE.
echo Restart using STOP_SERVER.bat then LAUNCH_APP.bat
pause
