@echo off
setlocal
cd /d "%~dp0"
echo =====================================================
echo JeevikaMitra V43 - Independent Local Setup
echo =====================================================
echo This setup never uses any older JeevikaMitra folder.
echo Python environment and speech models are prepared for this folder only.
echo Your .env is not read, printed, or changed by this setup.
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed or is not on PATH.
  echo Install Python 3.12, then run this file again.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Creating project-local Python environment...
  python -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo [1/4] Project-local Python environment already exists.
)

set "PYTHON_EXE=%CD%\.venv\Scripts\python.exe"
echo [2/4] Installing application dependencies...
"%PYTHON_EXE%" -m pip install --disable-pip-version-check --upgrade pip
if errorlevel 1 goto :fail
"%PYTHON_EXE%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :fail

echo [3/4] Preparing Indic-first jury microphone pack...
call PREPARE_JURY_MIC.bat
if errorlevel 1 goto :fail

echo [4/4] Preparing multilingual offline speech output...
call SETUP_OFFLINE_TTS.bat
if errorlevel 1 goto :fail
echo Offline multilingual speech output ready.

echo.
echo =====================================================
echo Independent local setup complete.
echo Everything JeevikaMitra itself needs is now in this folder.
echo Start with START_HYBRID.bat
echo =====================================================
pause
exit /b 0

:fail
echo.
echo Setup failed. Read the error above; no old project folder is required.
pause
exit /b 1
