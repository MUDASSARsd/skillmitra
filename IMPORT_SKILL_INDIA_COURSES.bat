@echo off
setlocal
if "%~1"=="" (
  echo Usage: IMPORT_SKILL_INDIA_COURSES.bat path\to\course_response.json
  exit /b 2
)
python scripts\import_skill_india_courses.py "%~1"
endlocal
