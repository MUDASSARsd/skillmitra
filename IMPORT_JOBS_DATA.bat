@echo off
setlocal
call "%~dp0_USE_PROJECT_PYTHON.bat"
set "PYTHON=%PYTHON_EXE%"
if "%~1"=="" (
  echo Usage: IMPORT_JOBS_DATA.bat path\to\jobs_response.json
  echo.
  echo Save the Skill India/NCS search Response as JSON and pass the file here.
  pause
  exit /b 1
)
"%PYTHON%" scripts\import_jobs.py "%~1"
if errorlevel 1 (
  echo Job import failed.
  pause
  exit /b 1
)
echo DONE.
pause
