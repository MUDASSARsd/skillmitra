@echo off
setlocal
cd /d "%~dp0"

call "%~dp0_USE_PROJECT_PYTHON.bat"
set "PYTHON=%PYTHON_EXE%"

echo ===============================================
echo SkillMitra Official NQR Eligibility Harvester V15.2
echo ===============================================
echo.
echo SEEDED MODE: uses the 2,814 real NQR qualification IDs captured from the official catalogue request.
echo This process is RESUMABLE. Ctrl+C will not erase prior progress.
echo It only stores eligibility found on official NQR pages.
echo.

"%PYTHON%" -c "import bs4, requests" >nul 2>&1
if errorlevel 1 (
  echo Installing BeautifulSoup dependency...
  "%PYTHON%" -m pip install beautifulsoup4
  if errorlevel 1 goto :error
)

echo [1/3] Refreshing already-known NQR eligibility pages...
"%PYTHON%" scripts\nqr_eligibility_harvester.py harvest-known
if errorlevel 1 goto :error

echo.
echo [2/3] Harvesting the 2,814 real official NQR qualification IDs...
echo No brute-force scan and no browser cookies/tokens are required.
"%PYTHON%" scripts\nqr_eligibility_harvester.py discover-catalogue
if errorlevel 1 goto :smart_error

echo.
echo [3/3] Importing harvested routes into SkillMitra SQLite...
"%PYTHON%" scripts\import_eligibility.py
if errorlevel 1 goto :error

echo.
echo DONE. Check data\eligibility_coverage_report.json
echo Discovered IDs are saved in data\nqr_discovered_ids.json
pause
exit /b 0

:smart_error
echo.
echo Seeded NQR harvesting failed. Your existing data is safe.
echo Copy the error above and send it to ChatGPT.
pause
exit /b 3

:error
echo.
echo Eligibility build failed. Copy the error above.
pause
exit /b 1
