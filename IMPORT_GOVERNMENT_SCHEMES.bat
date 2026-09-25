@echo off
setlocal
cd /d %~dp0
python import_government_schemes.py
if errorlevel 1 (
  echo Scheme import FAILED.
  exit /b 1
)
echo Government scheme snapshot imported successfully.
