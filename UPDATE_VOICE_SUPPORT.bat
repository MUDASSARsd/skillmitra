@echo off
setlocal
cd /d "%~dp0"
call "%~dp0_USE_PROJECT_PYTHON.bat"
"%PYTHON_EXE%" --version >nul 2>nul
if errorlevel 1 (
  echo Python environment not found. Run SETUP_PROJECT_ENV.bat first.
  pause
  exit /b 1
)
echo Installing/updating online multilingual voice support...
"%PYTHON_EXE%" -m pip install "edge-tts>=7,<8"
if errorlevel 1 (
  echo Voice support installation failed. Check internet access and try again.
  pause
  exit /b 1
)
echo.
echo Online multilingual TTS is ready for English, Hindi, Telugu, Tamil,
echo Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi and Odia.
echo No .env file was changed.
pause
