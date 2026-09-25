# JeevikaMitra V42 — Indic-first Offline Voice Fix

V42 leaves the already-working Online AI path unchanged and replaces the problematic generic-Whisper-first Offline Indian-language recognition path.

## Offline ASR

Primary jury pack:
- English — FastConformer ONNX
- Hindi — IndicConformer ONNX
- Telugu — IndicConformer ONNX
- Tamil — IndicConformer ONNX
- Hinglish — Indian-accented Hinglish Whisper ONNX

`SETUP_INDEPENDENT_LOCAL.bat` installs the primary jury pack. The models live only under `models/indicconformer-sherpa-onnx/` in this project.

For Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi and Odia, run `SETUP_ALL_OFFLINE_LANGUAGES.bat` once. After the models are downloaded, no internet is needed for Offline ASR.

Generic faster-whisper remains only as a backward-compatible fallback if an old project-local model happens to exist. It is no longer the preferred Hindi/Telugu/Tamil recognizer.

## Offline TTS

Offline mode now calls `/tts/offline` before trying any browser/system voice. This avoids the Windows/Chromium case where a voice is listed but produces no sound.

The project-local eSpeak NG path is passed explicitly with `--path` and `ESPEAK_DATA_PATH`, which is important for an MSI extracted into the project because it does not have the normal Windows registry installation metadata.

Run `TEST_OFFLINE_VOICE.bat` to generate and play a short phrase in every language exposed by the UI.

## Online mode

Online microphone, Online AI extraction/reasoning and Online TTS are intentionally unchanged in V42.
