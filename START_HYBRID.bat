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
set "PYTHONUTF8=1"

rem Do not block Online AI startup on Offline voice packs.
set "CORE_ASR_READY=1"
if not exist "models\indicconformer-sherpa-onnx\en\model.int8.onnx" set "CORE_ASR_READY="
if not exist "models\indicconformer-sherpa-onnx\hi\model.int8.onnx" set "CORE_ASR_READY="
if not exist "models\indicconformer-sherpa-onnx\te\model.int8.onnx" set "CORE_ASR_READY="
if not exist "models\indicconformer-sherpa-onnx\ta\model.int8.onnx" set "CORE_ASR_READY="
if defined CORE_ASR_READY (
  echo Offline jury microphone: Indic-first English/Hindi/Telugu/Tamil pack found.
) else (
  echo Offline jury microphone: high-accuracy pack is not fully installed.
  echo Online mode will still work. Run SETUP_INDEPENDENT_LOCAL.bat once for Offline jury voice.
)
echo.

echo ===============================================
echo JeevikaMitra V44 - Indic-first offline voice launcher
echo ===============================================
if not exist ".env" (
  rem copy .env.example to .env when the private local file is missing
  echo Online Gemini: .env not found. Creating it from .env.example ...
  copy /y ".env.example" ".env" >nul
  echo Add GEMINI_API_KEY to .env to enable online mode.
) else (
  findstr /b /c:"GEMINI_API_KEY=" .env | findstr /v /x "GEMINI_API_KEY=" >nul
  if errorlevel 1 (echo Online Gemini: API key not configured.) else (echo Online Gemini: API key configured.)
)

where ollama >nul 2>nul
if errorlevel 1 (
  echo Offline free-form NLU: Ollama command not found.
) else (
  ollama list | findstr /i "gemma3:4b" >nul
  if errorlevel 1 (echo Offline free-form NLU: gemma3:4b missing. Run: ollama pull gemma3:4b) else (echo Offline free-form NLU: gemma3:4b ready.)
  ollama list | findstr /i "gemma3:1b" >nul
  if errorlevel 1 (echo Optional speed model gemma3:1b is not installed.) else (echo Optional speed model gemma3:1b ready.)
)

"%PYTHON_EXE%" -c "from dotenv import load_dotenv; load_dotenv(); from backend.stt_local import LocalSTT; print(LocalSTT().status().detail)" 2>nul
"%PYTHON_EXE%" -c "from dotenv import load_dotenv; load_dotenv(); from backend.tts_local import LocalTTS; print(LocalTTS().status().detail)" 2>nul
if exist "data\nqr_semantic_embeddings.npz" (echo Semantic NQR mapping: local vector index ready.) else (echo Semantic NQR mapping: index missing - run BUILD_SEMANTIC_INDEX.bat when Ollama embedding model is available.)

echo.
powershell -Command "$c = Test-NetConnection -ComputerName 127.0.0.1 -Port 8000 -InformationLevel Quiet -WarningAction SilentlyContinue; if ($c) { exit 0 } else { exit 1 }" >nul 2>nul
if not errorlevel 1 (
  echo ==============================================================
  echo [INFO] JeevikaMitra is ALREADY running and healthy on port 8000!
  echo ==============================================================
  echo Opening application in your browser: http://127.0.0.1:8000/app
  start http://127.0.0.1:8000/app
  echo.
  echo To restart cleanly, double-click RESTART_SERVER.bat
  echo To stop the server, double-click STOP_SERVER.bat
  echo.
  pause
  exit /b 0
)

echo Starting JeevikaMitra at http://127.0.0.1:8000/app
echo Press Ctrl+C to stop.
"%PYTHON_EXE%" -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
pause

