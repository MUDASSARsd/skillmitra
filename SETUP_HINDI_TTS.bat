@echo off
setlocal
cd /d "%~dp0"
call "%~dp0_USE_PROJECT_PYTHON.bat"
"%PYTHON_EXE%" --version >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Run SETUP_PROJECT_ENV.bat first.
  pause
  exit /b 1
)
"%PYTHON_EXE%" setup_hindi_tts.py
if errorlevel 1 (
  echo.
  echo Hindi TTS setup did not finish. Read the error above.
  pause
  exit /b 1
)
echo.
echo Hindi TTS setup finished successfully.
pause
