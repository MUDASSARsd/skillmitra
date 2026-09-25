@echo off
setlocal
cd /d "%~dp0"
echo ===============================================
echo JeevikaMitra V43 - Offline microphone setup
echo ===============================================
echo One-time high-accuracy setup for jury languages.
echo No .env file is read or modified.
echo.
call "%~dp0PREPARE_JURY_MIC.bat"
if errorlevel 1 goto :fail
echo.
echo Offline microphone is ready for English/Hindi/Telugu/Tamil/Hinglish.
echo For every UI Indian language also run SETUP_ALL_OFFLINE_LANGUAGES.bat.
exit /b 0
:fail
echo.
echo Microphone setup failed. Keep internet on for this one-time setup and retry.
exit /b 1
