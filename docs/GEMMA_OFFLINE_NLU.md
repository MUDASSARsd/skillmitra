# SkillMitra — Free-form Multilingual Offline NLU

Offline conversation understanding now uses **Gemma 3 4B through Ollama as the primary extractor**.
The older deterministic LocalProfileExtractor is **not used by default**. This prevents the app from silently falling back to predefined phrase rules. It can be enabled only with `OLLAMA_ALLOW_RULE_FALLBACK=1` for emergency debugging.

## Architecture

- English speech -> Parakeet ASR
- Hindi/Telugu speech -> AI4Bharat IndicConformer
- Transcript -> Gemma 3 4B (Ollama, local) -> structured BeneficiaryProfile
- BeneficiaryProfile -> deterministic NQR mapping, eligibility and ranking

The LLM is not allowed to invent courses, schemes, centres or eligibility decisions.

## One-time setup

```powershell
ollama pull gemma3:4b
```

Ollama should be running locally on `http://127.0.0.1:11434`.

## Status check

With the backend running, open:

`http://127.0.0.1:8000/nlu/offline/status`

Expected:

```json
{
  "ready": true,
  "server_ready": true,
  "model": "gemma3:4b"
}
```

## Why normalization still exists

The LLM performs language understanding. A small post-processing step only converts equivalent meanings into stable internal values, e.g. `tenth pass` -> `10th`, `two years` -> `24 months`, `start own business` -> `business`. It does not use phrase lists to understand the user.
