# JeevikaMitra V44 — Offline Hindi + Audio Reliability Fix

V44 is a focused stabilization patch on top of V43. The working Online path is unchanged.

Key fixes:
- Hindi IndicConformer near-spellings such as `इलेक्ट्रेशन` are canonicalized to the electrical/electrician skill in clear work-context sentences.
- Existing contextual education correction remains active, so `10वीं कक्षा` and common noisy 10th-class variants do not loop.
- Offline TTS now uses the generated WAV in the browser first, through an AudioContext primed during the user's mic/send gesture.
- Windows direct playback is fallback-only and now calls `winsound.PlaySound(..., SND_ASYNC)` before reporting success, so background-thread failures cannot masquerade as successful speech.
- Online mode is intentionally unchanged.

Run `SETUP_INDEPENDENT_LOCAL.bat` once for a fresh folder, then `START_HYBRID.bat` and hard refresh with Ctrl+F5.
