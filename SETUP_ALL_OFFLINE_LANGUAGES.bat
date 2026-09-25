@echo off
setlocal
cd /d "%~dp0"
title JeevikaMitra V43 Full Offline Language Pack
call "%~dp0_USE_PROJECT_PYTHON.bat"
echo ============================================================
echo   JeevikaMitra V43 - Full Offline Indian-Language ASR Pack
echo ============================================================
echo.
echo This downloads high-accuracy IndicConformer ONNX models for:
echo Hindi Telugu Tamil Kannada Malayalam Marathi Bengali Gujarati
echo Punjabi and Odia, plus English FastConformer.
echo.
echo This is a LARGE one-time download (roughly 2 GB total).
echo After download, speech recognition works without internet.
echo No .env file is read or changed.
echo.
"%PYTHON_EXE%" -m pip install --disable-pip-version-check "sherpa-onnx>=1.13,<2" "sherpa-onnx-bin>=1.13,<2" "huggingface-hub>=0.26,<2"
if errorlevel 1 goto :fail
"%PYTHON_EXE%" setup_indic_sherpa.py --all
if errorlevel 1 goto :fail
echo.
echo Full Offline language pack is READY.
echo Restart START_HYBRID.bat and press Ctrl+F5 in the browser.
exit /b 0
:fail
echo.
echo [ERROR] Full Offline language-pack setup failed.
echo Keep internet on during this one-time download and retry.
exit /b 1
