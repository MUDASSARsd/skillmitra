@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo JeevikaMitra V41 - project-local Python environment setup
echo ===============================================
where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found on PATH. Install Python 3.12 first.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating local .venv ...
  python -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo [1/3] Local .venv already exists.
)
set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
echo [2/3] Installing core app dependencies ...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%PYTHON_EXE%" -m pip install -r requirements.txt
if errorlevel 1 goto :fail
echo [3/3] Core environment ready.
if not exist ".env" copy /y ".env.example" ".env" >nul

echo.
echo Recommended offline voice input setup:
echo   SETUP_OFFLINE_STT.bat
echo Advanced Parakeet / AI4Bharat engines can still use requirements-asr.txt.
echo Optional Telugu offline voice output:
echo   SETUP_TELUGU_TTS.bat
echo Optional free-form offline NLU requires Ollama + gemma3:4b.
echo Online mode requires GEMINI_API_KEY in .env.
echo.
echo Start the app with START_HYBRID.bat
pause
exit /b 0
:fail
echo.
echo Setup failed. Copy the error above.
pause
exit /b 1
