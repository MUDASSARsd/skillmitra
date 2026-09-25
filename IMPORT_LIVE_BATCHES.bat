@echo off
setlocal
if "%~1"=="" (
  echo Usage: IMPORT_LIVE_BATCHES.bat path\to\skill_india_batch_response.json
  exit /b 1
)
python scripts\import_live_batches.py "%~1" --replace-source
endlocal
