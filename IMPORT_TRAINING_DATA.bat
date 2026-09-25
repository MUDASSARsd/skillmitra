@echo off
setlocal
call "%~dp0_USE_PROJECT_PYTHON.bat"
set "PY=%PYTHON_EXE%"
if "%~1"=="" (
  echo Usage: IMPORT_TRAINING_DATA.bat path\to\official_training_snapshot.csv
  echo.
  echo Use data\training_centres_template.csv as the required column template.
  exit /b 2
)
"%PY%" scripts\import_training_centres.py "%~1"
endlocal
