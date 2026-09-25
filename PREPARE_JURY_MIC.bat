@echo off
setlocal
cd /d "%~dp0"
call "%~dp0_USE_PROJECT_PYTHON.bat"
"%PYTHON_EXE%" --version >nul 2>nul
if errorlevel 1 exit /b 1

echo ============================================================
echo   JeevikaMitra V43 - Jury Offline Microphone Setup
echo ============================================================
echo.
echo Primary Offline ASR is now Indic-first ONNX, not generic Whisper.
echo This default jury pack installs English + Hindi + Telugu + Tamil + Hinglish.
echo Use SETUP_ALL_OFFLINE_LANGUAGES.bat later for Kannada, Malayalam,
echo Marathi, Bengali, Gujarati, Punjabi and Odia.
echo No .env file is read or modified.
echo.

echo [Mic 1/3] Installing on-device ASR runtimes...
"%PYTHON_EXE%" -m pip install --disable-pip-version-check "sherpa-onnx>=1.13,<2" "sherpa-onnx-bin>=1.13,<2" "huggingface-hub>=0.26,<2" "faster-whisper>=1.1,<2"
if errorlevel 1 exit /b 1

echo [Mic 2/3] Preparing Hindi/Telugu/Tamil/Hinglish Indic-first jury models...
"%PYTHON_EXE%" setup_indic_sherpa.py
if errorlevel 1 exit /b 1

echo [Mic 3/3] Preparing Whisper Small for higher-quality Indian English...
"%PYTHON_EXE%" setup_offline_stt.py
if errorlevel 1 exit /b 1

echo.
echo Jury Offline microphone pack is READY.
exit /b 0
