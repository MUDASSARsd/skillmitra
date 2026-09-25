@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title JeevikaMitra V43 Offline Multilingual TTS Setup
call "%~dp0_USE_PROJECT_PYTHON.bat"

set "TOOLROOT=%CD%\tools\espeak-ng"
set "MSI=%TEMP%\jeevikamitra-espeak-ng-1.52.0.msi"
set "ESPEAK_FOUND="

echo ============================================================
echo   JeevikaMitra V43 - Offline Multilingual Speech Setup
echo ============================================================
echo.
echo This prepares eSpeak NG for the current JeevikaMitra folder.
echo Telugu, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati,
echo Punjabi, Odia, Hindi and English then work without internet.
echo Hindi/Telugu still prefer Piper automatically if those voices exist.
echo No .env file is read or changed by this setup.
echo It is never printed either.
echo.

rem 1) Reuse a project-local copy if it already exists.
if exist "%TOOLROOT%" (
  for /r "%TOOLROOT%" %%F in (espeak-ng.exe) do if not defined ESPEAK_FOUND set "ESPEAK_FOUND=%%F"
)
if defined ESPEAK_FOUND goto :validate

rem 2) Reuse a normal Windows installation if present.
where espeak-ng.exe >nul 2>nul
if not errorlevel 1 (
  for /f "delims=" %%F in ('where espeak-ng.exe') do if not defined ESPEAK_FOUND set "ESPEAK_FOUND=%%F"
)
if exist "C:\Program Files\eSpeak NG\espeak-ng.exe" set "ESPEAK_FOUND=C:\Program Files\eSpeak NG\espeak-ng.exe"
if exist "C:\Program Files (x86)\eSpeak NG\espeak-ng.exe" set "ESPEAK_FOUND=C:\Program Files (x86)\eSpeak NG\espeak-ng.exe"
if defined ESPEAK_FOUND goto :validate

rem 3) Preferred independent install: download official MSI and administratively
rem    extract it under this project. No PATH change and no old project required.
echo [TTS 1/2] Preparing a project-local eSpeak NG copy...
if not exist "%TOOLROOT%" mkdir "%TOOLROOT%" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ProgressPreference='SilentlyContinue'; Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/espeak-ng/espeak-ng/releases/download/1.52.0/espeak-ng.msi' -OutFile '%MSI%'"
if not errorlevel 1 if exist "%MSI%" (
  msiexec /a "%MSI%" /qn TARGETDIR="%TOOLROOT%\package"
)
if exist "%TOOLROOT%" (
  for /r "%TOOLROOT%" %%F in (espeak-ng.exe) do if not defined ESPEAK_FOUND set "ESPEAK_FOUND=%%F"
)
if defined ESPEAK_FOUND goto :validate

rem 4) Fallback to Windows Package Manager if administrative extraction is blocked.
where winget.exe >nul 2>nul
if errorlevel 1 goto :fail

echo Project-local extraction was unavailable. Trying Windows Package Manager...
winget install -e --id eSpeak-NG.eSpeak-NG --silent --accept-package-agreements --accept-source-agreements
where espeak-ng.exe >nul 2>nul
if not errorlevel 1 for /f "delims=" %%F in ('where espeak-ng.exe') do if not defined ESPEAK_FOUND set "ESPEAK_FOUND=%%F"
if exist "C:\Program Files\eSpeak NG\espeak-ng.exe" set "ESPEAK_FOUND=C:\Program Files\eSpeak NG\espeak-ng.exe"
if exist "C:\Program Files (x86)\eSpeak NG\espeak-ng.exe" set "ESPEAK_FOUND=C:\Program Files (x86)\eSpeak NG\espeak-ng.exe"
if not defined ESPEAK_FOUND goto :fail

:validate
echo [TTS 2/2] Validating every UI language with the local backend...
"%PYTHON_EXE%" -c "from backend.tts_local import LocalTTS; t=LocalTTS(); langs=[('en','Hello'),('hi','नमस्ते'),('te','నమస్తే'),('ta','வணக்கம்'),('kn','ನಮಸ್ಕಾರ'),('ml','നമസ്കാരം'),('mr','नमस्कार'),('bn','নমস্কার'),('gu','નમસ્તે'),('pa','ਸਤ ਸ੍ਰੀ ਅਕਾਲ'),('or','ନମସ୍କାର')]; files=[]; [(files.append(t.synthesize(x,l))) for l,x in langs]; [p.unlink(missing_ok=True) for p in files]; print('Offline multilingual TTS validation passed for all UI languages.')"
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo   Offline multilingual TTS is READY.
echo ============================================================
echo Engine: %ESPEAK_FOUND%
echo Restart START_HYBRID.bat and refresh the browser with Ctrl+F5.
echo.
exit /b 0

:fail
echo.
echo [ERROR] Offline multilingual TTS setup/validation failed.
echo Internet is needed only for this one-time setup.
echo Re-run this file and copy the error shown above if it still fails.
echo.
exit /b 1
