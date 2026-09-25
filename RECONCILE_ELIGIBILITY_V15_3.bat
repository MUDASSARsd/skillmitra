@echo off
setlocal
cd /d "%~dp0"

call "%~dp0_USE_PROJECT_PYTHON.bat"
set "PYTHON=%PYTHON_EXE%"

echo ===============================================
echo SkillMitra Eligibility Reconciliation V15.3
echo ===============================================
echo.
echo WHY THIS PASS EXISTS:
echo V15.2 recognized legacy codes such as 2022/HLT/HSSC/06763,
echo but most current local NQR records use codes such as

echo NG-2.5-AG-00738-2023-V1-ASCI.
echo.
echo This pass revisits ONLY currently-unmapped official NQR IDs,
echo recognizes old + current code formats, harvests verified eligibility,
echo and keeps the 331 mappings / 1206 routes you already collected.
echo.
echo It is safe to stop with Ctrl+C. Existing CSV/SQLite data is preserved.
echo.

"%PYTHON%" -c "import bs4, requests, pandas" >nul 2>&1
if errorlevel 1 (
  echo Installing required dependencies...
  "%PYTHON%" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)

echo [1/3] Re-scanning currently-unmapped official NQR IDs with the expanded code parser...
"%PYTHON%" scripts\nqr_eligibility_harvester.py discover-catalogue --no-resume --skip-known
if errorlevel 1 goto :error

echo.
echo [2/3] Importing all verified eligibility routes into SQLite...
"%PYTHON%" scripts\import_eligibility.py
if errorlevel 1 goto :error

echo.
echo [3/3] Final coverage report:
type data\eligibility_coverage_report.json
echo.
echo Import report:
type data\eligibility_import_report.json

echo.
echo DONE. Send the two reports above to ChatGPT.
pause
exit /b 0

:error
echo.
echo Reconciliation failed. Existing harvested data is safe.
echo Copy the error above and send it to ChatGPT.
pause
exit /b 1
