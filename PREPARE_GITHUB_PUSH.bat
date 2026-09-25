@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo   SkillMitra - Prepare & Push to GitHub for Render
echo ========================================================
echo.

where git >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Git is not installed or not in PATH.
    echo Please install Git from https://git-scm.com/downloads
    pause
    exit /b 1
)

if not exist ".git" (
    echo [1/4] Initializing Git repository...
    git init
    git branch -M main
) else (
    echo [1/4] Git repository already initialized.
)

echo [2/4] Staging clean deployment files...
git add .

echo [3/4] Creating commit...
git commit -m "SkillMitra: SIH Production Release for Render"

echo.
echo ========================================================
echo [4/4] Connect your GitHub Repository
echo ========================================================
echo.
echo If you created an empty repo on GitHub (e.g. https://github.com/USERNAME/skillmitra.git),
set /p REPO_URL="Paste your GitHub Repo URL here (or press Enter to skip): "

if not "%REPO_URL%"=="" (
    git remote remove origin >nul 2>nul
    git remote add origin %REPO_URL%
    echo Pushing code to GitHub...
    git push -u origin main
    echo.
    echo Successfully pushed to GitHub!
) else (
    echo.
    echo Whenever you are ready, run:
    echo   git remote add origin ^<your-repo-url^>
    echo   git push -u origin main
)

echo.
pause
