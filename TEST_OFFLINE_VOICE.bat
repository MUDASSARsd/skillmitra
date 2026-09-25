@echo off
setlocal
cd /d "%~dp0"
call "%~dp0_USE_PROJECT_PYTHON.bat"
echo Testing local speech generation and Windows playback for every UI language...
"%PYTHON_EXE%" -c "from backend.tts_local import LocalTTS; import winsound; tests=[('en','Hello'),('hi','नमस्ते'),('te','నమస్తే'),('ta','வணக்கம்'),('kn','ನಮಸ್ಕಾರ'),('ml','നമസ്കാരം'),('mr','नमस्कार'),('bn','নমস্কার'),('gu','નમસ્તે'),('pa','ਸਤ ਸ੍ਰੀ ਅਕਾਲ'),('or','ନମସ୍କାର')]; t=LocalTTS(); [(print('Playing',l), (lambda p:(winsound.PlaySound(str(p), winsound.SND_FILENAME), p.unlink(missing_ok=True)))(t.synthesize(x,l))) for l,x in tests]"
if errorlevel 1 (
  echo Offline TTS test FAILED.
  exit /b 1
)
echo Offline TTS test PASSED for every UI language.
exit /b 0
