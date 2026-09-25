@echo off
setlocal
cd /d "%~dp0"
python sync_kaushal_bharat.py
if errorlevel 1 (
  echo Sync failed. Check internet connection and Python dependencies.
  exit /b 1
)
echo Official Kaushal Bharat directory sync complete.
