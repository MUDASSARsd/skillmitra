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
echo.
echo [1/4] Checking Python code...
"%PYTHON_EXE%" -m compileall -q backend tests
if errorlevel 1 goto :fail

echo [2/4] Running deterministic and mocked regression tests...
"%PYTHON_EXE%" -m pytest -q tests/test_models.py tests/test_conversation.py tests/test_local_extractor.py tests/test_mapping.py tests/test_eligibility_engine.py tests/test_recommendation_engine.py tests/test_ollama_extractor.py tests/test_online_extractor.py tests/test_api.py tests/test_frontend.py tests/test_voice_frontend.py tests/test_v3_fixes.py tests/test_stability_matrix.py tests/test_semantic_mapping.py tests/test_v29_multilingual_languages.py
if errorlevel 1 goto :fail

echo [3/4] Checking local models/assets...
where ollama >nul 2>nul
if errorlevel 1 (
  echo WARNING: Ollama not installed or not on PATH.
) else (
  ollama list | findstr /i "gemma3:4b" >nul || echo WARNING: gemma3:4b not found
  ollama list | findstr /i "gemma3:1b" >nul || echo WARNING: gemma3:1b not found
  ollama list | findstr /i "embeddinggemma" >nul || echo WARNING: embeddinggemma not found - run BUILD_SEMANTIC_INDEX.bat
)
"%PYTHON_EXE%" -c "from dotenv import load_dotenv; load_dotenv(); from backend.stt_local import LocalSTT; print(LocalSTT().status().detail)"
"%PYTHON_EXE%" -c "from dotenv import load_dotenv; load_dotenv(); from backend.tts_local import LocalTTS; print(LocalTTS().status().detail)"
if exist "data\nqr_semantic_embeddings.npz" (echo Semantic NQR index: OK) else (echo WARNING: Semantic NQR index missing - run BUILD_SEMANTIC_INDEX.bat)

echo [4/4] Stability test complete.
echo NOTE: Microphone/audio hardware and live Gemini require a manual test on the laptop.
pause
exit /b 0
:fail
echo Stability tests FAILED. Copy the error above.
pause
exit /b 1
