# JeevikaMitra V39 — Stabilized Independent Local Build

This is the pre-deployment stabilization build. It is independent of V30–V38 folders.

## Reliability changes
- Offline conversation never requires Ollama; deterministic multilingual extraction is always available.
- Repeated already-known answers do not trigger unnecessary Gemini calls.
- Ambiguous employment replies are clarified instead of guessed.
- Hindi counter-questions use Devanagari; Hinglish remains Romanized.
- Deterministic offline core covers all selectable UI languages for common education, experience, job-preference and training flows.
- Offline core readiness no longer falsely depends on microphone/TTS installation.
- Frontend assets use V39 cache-busting to avoid stale JavaScript after updates.
- Local model paths remain project-relative by default.

## Validation
- Full automated test suite: 259 passed.
- Python compile check: passed.
- Frontend JavaScript syntax check: passed.
- `nqr_database.db` SQLite integrity: OK.
- NQR qualifications: 2814.
- Eligibility routes: 11222.
- Semantic index: 2814 x 768 vectors loaded successfully.
- Runtime scan found no references to older JeevikaMitra version folders.

Deployment is intentionally deferred until this build is tested on the target Windows laptop with real microphone/speaker hardware.
