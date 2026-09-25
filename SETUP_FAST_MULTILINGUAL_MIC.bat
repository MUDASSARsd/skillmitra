@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo JeevikaMitra V43 - Indic-first Offline Mic
echo ===============================================
echo This no longer installs generic Whisper as the primary Indian-language engine.
echo It prepares the jury ONNX pack for English, Hindi, Telugu, Tamil and Hinglish.
echo This script does NOT read or modify .env.
echo.
call "%~dp0PREPARE_JURY_MIC.bat"
