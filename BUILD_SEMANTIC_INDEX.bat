@echo off
setlocal
cd /d "%~dp0"
call "%~dp0_USE_PROJECT_PYTHON.bat"
"%PYTHON_EXE%" --version >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Run SETUP_PROJECT_ENV.bat first.
  pause
  exit /b 1
)
where ollama >nul 2>nul
if errorlevel 1 (
  echo Ollama is not installed or not on PATH.
  pause
  exit /b 1
)
echo [1/3] Checking multilingual embedding model...
ollama list | findstr /i "embeddinggemma" >nul
if errorlevel 1 (
  echo Downloading EmbeddingGemma once...
  ollama pull embeddinggemma
  if errorlevel 1 goto :fail
)
echo [2/3] Building embeddings for all official local NQR qualifications...
"%PYTHON_EXE%" build_semantic_index.py
if errorlevel 1 goto :fail
echo [3/3] Running semantic mapping smoke tests...
"%PYTHON_EXE%" semantic_smoke_test.py
if errorlevel 1 goto :fail
echo.
echo Semantic NQR mapping is ready.
pause
exit /b 0
:fail
echo.
echo Semantic mapping setup FAILED. Copy the error above.
pause
exit /b 1
