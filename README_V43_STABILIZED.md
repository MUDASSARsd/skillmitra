# JeevikaMitra V43 — Jury Offline Reliability Fix

V43 leaves the working Online path unchanged. It fixes the real-laptop Offline issues observed in V42:

- noisy education ASR answers such as `Tend the glass`, `teninth`, `टैेंथ क्लास` are contextually normalized to 10th instead of causing loops;
- Offline English prefers faster-whisper Small for Indian-accented English; Hindi/Telugu/Tamil remain IndicConformer-first;
- common observed electrician ASR variants are normalized by the deterministic local extractor;
- Offline Windows local mode can play generated TTS directly through the backend speaker path, bypassing browser autoplay issues;
- browser WAV/System TTS fallbacks remain available when direct local playback is unavailable;
- Online voice/NLU/TTS routing is unchanged.

Run `SETUP_INDEPENDENT_LOCAL.bat` once, then `START_HYBRID.bat`.
