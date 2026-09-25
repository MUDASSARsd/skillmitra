# JeevikaMitra V40 — Stabilized Multilingual Voice Build

V40 is a local pre-deployment stabilization build.

## Fixes in V40

- Telugu training willingness accepts natural replies such as `సిద్ధంగా ఉన్నా` and `సిద్దంగా ఉన్నా`.
- Equivalent natural ready/yes replies are covered for Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi and Odia.
- The UI-selected language is authoritative; counter-questions cannot silently switch Telugu into Hinglish.
- Malformed optional Ollama JSON never reaches the beneficiary UI; Offline conversation falls back to deterministic rules.
- Offline microphone setup now installs `Systran/faster-whisper-base` instead of Tiny for materially better Indic ASR quality.
- Indic local ASR uses language-specific native-script prompts, beam search, VAD, and rejects obvious wrong-script hallucinations before auto-send.
- `SETUP_INDEPENDENT_LOCAL.bat` now installs multilingual offline TTS (eSpeak NG) as part of the one-time independent setup.
- Frontend keeps generated audio alive and awaits speech start, preventing local TTS playback from being lost during UI updates.
- Online microphone/transcription remains on the low-latency cloud path.

## First setup

Run `SETUP_INDEPENDENT_LOCAL.bat` once with internet available. It creates the project-local Python environment, downloads the project-local Base multilingual ASR model, and installs the offline multilingual speech engine.

Then run `START_HYBRID.bat`.

## Important

The project does not require any previous JeevikaMitra version folder. Offline model files are placed under this V40 project or installed as the local speech engine.
