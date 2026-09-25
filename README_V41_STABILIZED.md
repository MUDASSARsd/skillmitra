# JeevikaMitra V41 — Offline Voice Hardening

V41 keeps the Online AI path unchanged because Online speech is already working well.

## Offline microphone fixes
- Uses project-local `faster-whisper-small` as the preferred jury model.
- Keeps base/tiny only as backward-compatible fallbacks.
- Adds stricter VAD and decoding settings, repetition penalty, no-repeat n-grams, and a short-output cap.
- Rejects repeated-character and repeated-word hallucinations instead of auto-sending garbage to the conversation.
- Stops any assistant speech before microphone capture so the assistant cannot be recorded into the next turn.

## Offline speech-output fixes
- Prepares eSpeak NG project-locally when possible, with a Windows installation fallback.
- Validates Hindi, Telugu, and Tamil speech during setup.
- Uses a user-unlocked Web Audio context for backend WAV playback so Chromium does not silently block async local TTS.
- Includes `TEST_OFFLINE_VOICE.bat` for direct laptop speaker testing.

## Setup
Run `SETUP_INDEPENDENT_LOCAL.bat` once with internet available. Then run `START_HYBRID.bat`.

No previous JeevikaMitra folder is required.
