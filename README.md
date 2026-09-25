# JeevikaMitra — Final SIH Build

AI voice assistant for livelihood profiling and NSQF-aligned recommendations.

## Clean project layout

- `backend/` — API, conversation, NLU, STT/TTS, recommendation and evidence layers
- `frontend/` — jury/demo UI
- `data/` — local NQR/eligibility/course/job/training/scheme evidence
- `models/` — project-local voice/model assets when installed
- `scripts/` — import and maintenance scripts
- `tools/` — one-off extraction/index utilities
- `tests/` — automated tests
- `docs/` — architecture/reference notes

## First run

1. Keep your existing private `.env` locally. It is intentionally NOT included in this package.
2. Run `SETUP_PROJECT_ENV.bat` if the project environment is not ready.
3. For reliable offline microphone input on a fresh laptop, run `SETUP_OFFLINE_STT.bat` once. It installs a project-local multilingual Whisper fallback and does not require `.env`.
4. Optional offline spoken output: run `SETUP_TELUGU_TTS.bat` and/or `SETUP_HINDI_TTS.bat`.
5. If you are reusing an older venv, run `UPDATE_VOICE_SUPPORT.bat` once for online multilingual TTS. New `SETUP_PROJECT_ENV.bat` installs it automatically through `requirements.txt`.
6. Start with `START_HYBRID.bat`.
7. Open `/app` and hard-refresh with Ctrl+F5 after replacing frontend files.

## Voice behavior

- **Online output:** uses the browser/OS voice when available, then the `edge-tts` multilingual fallback for English, Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi and Odia. Online mode no longer requires Telugu Piper.
- **Offline output:** remains local. Hindi/Telugu can use Piper when installed; other languages keep a text reply unless a local matching voice is available.
- **Offline input:** first uses local ASR. Parakeet/AI4Bharat remain preferred when configured; `SETUP_OFFLINE_STT.bat` adds a project-local faster-whisper fallback that covers all UI languages. If no Python ASR is ready, the UI also tries browser on-device speech recognition instead of blocking the mic immediately.
- If online multilingual speech is missing in an existing venv, run `UPDATE_VOICE_SUPPORT.bat` once. This does not change `.env`.
- Very short/empty local recordings are rejected before model inference, preventing the previous TorchScript padding crash.

## Demo tip

For Hindi/Telugu offline voice:
tap mic -> speak for at least 1 second -> tap mic again -> review transcript -> Send.

Recommendations are intentionally withheld until the guided beneficiary profile is complete.

### Offline multilingual speech output (V32)

If Offline mode shows `/tts/offline` `503 Service Unavailable` or says that a local voice is unavailable, run `SETUP_OFFLINE_TTS.bat` once. It installs eSpeak NG as a compact offline fallback for all languages shown in the UI. Existing Piper Hindi/Telugu voices remain preferred automatically when available. Restart `START_HYBRID.bat` and hard-refresh the browser after setup.

## V33 fast multilingual microphone
Run `SETUP_FAST_MULTILINGUAL_MIC.bat` once. It installs/downloads one project-local
multilingual faster-whisper model. After that, Telugu, Tamil, Hindi, Kannada,
Malayalam, Marathi, Bengali, Gujarati, Punjabi and Odia microphone input works
locally in Offline mode, and Online AI mode reuses the same fast local transcript
before sending text to the online reasoning path. AI4Bharat IndicConformer remains
optional rather than required.
