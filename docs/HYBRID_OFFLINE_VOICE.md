# Hybrid Offline Voice — SkillMitra

## Routing

- English (`en`) -> sherpa-onnx + Parakeet 110M int8
- Hindi (`hi`), Telugu (`te`) and supported Indic language codes -> AI4Bharat IndicConformer 600M
- whisper.cpp -> optional fallback only, if `WHISPER_CPP_BIN` and `WHISPER_MODEL_PATH` remain configured

The recommendation engine is unchanged and remains deterministic/local.

## Important: launch with Python 3.12 venv

The AI4Bharat and sherpa packages were installed in `venv312`, so launch this app from that environment, not the system Python 3.14 interpreter.

```powershell
cd C:\Users\Sanjana\Documents\indic_asr_test
venv312\Scripts\activate
python -m pip install -r "C:\PATH\TO\sih_final\requirements.txt"
cd "C:\PATH\TO\sih_final"
python -m uvicorn backend.api.app:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/stt/offline/status` first. It should report `english_ready: true` and `indic_ready: true`.

Then open `http://127.0.0.1:8000/app`, choose **Offline local**, select English/Hindi/Telugu, and use the microphone.

## Same-language responses

The language selector is carried through the conversation. Counter-questions now have English, Hindi and Telugu versions, and browser TTS uses `en-IN`, `hi-IN`, or `te-IN` accordingly. Official NQR qualification titles remain as stored in the NQR database.

## Offline requirement

AI4Bharat must already be present in the Hugging Face cache. `INDIC_LOCAL_ONLY=1` prevents the app from attempting a network fetch at runtime.

## V30 voice reliability fix

- `voiceStatus` and `voiceModeText` are separate DOM elements so status updates no longer delete the mode-status element.
- Offline microphone routing no longer stops at a missing Python ASR status. It attempts browser on-device recognition when supported.
- Online TTS is separate from offline Piper. Missing Telugu Piper can no longer break Telugu speech in Online mode.
- `UPDATE_VOICE_SUPPORT.bat` installs the lightweight online multilingual TTS dependency without changing `.env`.

### Portable offline microphone fallback

For a fresh laptop, run `SETUP_OFFLINE_STT.bat` once while internet is available. It installs `faster-whisper` and downloads the multilingual base model into `models/faster-whisper-base`. After that, microphone transcription can run locally without an API key or `.env` path configuration. Parakeet and AI4Bharat are still used first when they are available.

## Multilingual offline TTS fallback (V32)

Run `SETUP_OFFLINE_TTS.bat` once on Windows. It installs eSpeak NG as a compact local fallback for English, Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi and Odia. The app still prefers project-local Piper for Hindi/Telugu when those higher-quality voices are installed. After the one-time install, fallback synthesis is local and does not require internet.
