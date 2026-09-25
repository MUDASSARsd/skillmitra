"""
Real Google AI API Integration Test Suite.
Dynamically discovers the first working model and runs all 5 extraction tests.

Key findings from model probe:
- gemini-2.5-flash / gemini-2.5-pro → 404 "not available to new users"
- gemma-4-26b-a4b-it → 200 SUCCESS (this is what we use)
"""
import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.models.beneficiary import BeneficiaryProfile
from backend.nlu.online_extractor import SYSTEM_EXTRACTION_PROMPT

# ──────────────────────────────────────────────────────────────────────────────
# LOW-LEVEL CALLER  (avoids responseMimeType which some models reject)
# ──────────────────────────────────────────────────────────────────────────────

def call_google_ai(model_name: str, api_key: str, prompt: str, user_text: str, timeout: int = 30) -> str:
    """
    Calls the Google AI generateContent endpoint.
    Uses the full model path e.g. 'models/gemma-4-26b-a4b-it'.
    Returns the raw text string from the first candidate.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent"
    combined = f"{prompt}\n\nUSER INPUT:\n\"{user_text}\"\n\nJSON OUTPUT:"
    payload = {
        "contents": [{"parts": [{"text": combined}]}],
        "generationConfig": {"temperature": 0.0}
    }
    resp = requests.post(url, params={"key": api_key}, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


# ──────────────────────────────────────────────────────────────────────────────
# MODEL DISCOVERY
# ──────────────────────────────────────────────────────────────────────────────

def discover_working_model(api_key: str) -> tuple[str, str]:
    """
    Queries /v1beta/models and probes each with a tiny generateContent call.
    Returns (model_display_name, full_model_path) of the first one that returns 200.
    """
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    try:
        data = requests.get(url, params={"key": api_key}, timeout=10).json()
    except requests.RequestException as exc:
        raise RuntimeError("Google AI model discovery failed. Check internet/DNS and API configuration.") from None
    all_models = [m["name"] for m in data.get("models", [])
                  if "generateContent" in m.get("supportedGenerationMethods", [])]

    print(f"Models declared as generateContent-capable: {len(all_models)}")

    # Prefer Gemini models, then fall through to Gemma
    preferred = [m for m in all_models if "gemini" in m]
    rest      = [m for m in all_models if "gemini" not in m]

    for model_path in preferred + rest:
        try:
            probe_url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent"
            r = requests.post(
                probe_url,
                params={"key": api_key},
                json={"contents": [{"parts": [{"text": "hi"}]}]},
                timeout=12
            )
            print(f"  {model_path} → {r.status_code}")
            if r.status_code == 200:
                display = model_path.replace("models/", "")
                print(f"\n✓ SELECTED WORKING MODEL: {model_path}")
                return display, model_path
        except Exception as e:
            print(f"  {model_path} → ERROR: provider connection failed")

    raise RuntimeError("No working model found under this API key.")


# ──────────────────────────────────────────────────────────────────────────────
# JSON CLEANING
# ──────────────────────────────────────────────────────────────────────────────

import re

def clean_json(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r'^```(?:json)?\s*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*```$', '', s)
    return s.strip()


# ──────────────────────────────────────────────────────────────────────────────
# SINGLE-TEST RUNNER
# ──────────────────────────────────────────────────────────────────────────────

def run_test(model_path: str, api_key: str, text: str,
             current_profile: BeneficiaryProfile = None) -> dict:
    t0 = time.perf_counter()
    raw = call_google_ai(model_path, api_key, SYSTEM_EXTRACTION_PROMPT, text, timeout=40)
    latency_ms = round((time.perf_counter() - t0) * 1000, 1)

    cleaned = clean_json(raw)

    pydantic_ok = False
    profile = None
    error = None
    try:
        d = json.loads(cleaned)
        extracted = BeneficiaryProfile.model_validate(d)
        pydantic_ok = True
        if current_profile:
            profile = current_profile.merge(extracted)
        else:
            profile = extracted
    except Exception as e:
        error = str(e)

    return {
        "input": text,
        "raw_response": raw,
        "pydantic_ok": pydantic_ok,
        "profile": profile,
        "error": error,
        "latency_ms": latency_ms,
    }


# ──────────────────────────────────────────────────────────────────────────────
# REPORT PRINTER
# ──────────────────────────────────────────────────────────────────────────────

def print_report(title: str, result: dict, analysis: str = ""):
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  {title}")
    print(sep)
    print(f"\n[1] EXACT USER INPUT:\n  \"{result['input']}\"")
    print(f"\n[2] RAW MODEL RESPONSE:\n{result['raw_response']}")
    print(f"\n[3] VALIDATED BeneficiaryProfile JSON:")
    if result["profile"]:
        print(result["profile"].model_dump_json(indent=2))
    else:
        print(f"  VALIDATION FAILED: {result['error']}")
    print(f"\n[4] Pydantic validation passed : {result['pydantic_ok']}")
    print(f"[5] API latency                : {result['latency_ms']} ms")
    if analysis:
        print(f"\n[6] FIELD ANALYSIS:\n{analysis}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    if not api_key:
        print("ERROR: GEMINI_API_KEY not set in .env")
        return

    print("=" * 70)
    print("  STEP 1 — DISCOVERING WORKING MODEL FROM GOOGLE AI API")
    print("=" * 70)
    model_display, model_path = discover_working_model(api_key)
    print(f"\nACTIVE MODEL  : {model_display}")
    print(f"FULL PATH     : {model_path}")
    print(f"PROVIDER      : Google AI (generativelanguage.googleapis.com)")

    print("\n" + "=" * 70)
    print("  STEP 2 — RUNNING 5 REAL EXTRACTION TESTS")
    print("=" * 70)

    # ── TEST 1: Hinglish ──────────────────────────────────────────────────────
    t1 = run_test(model_path, api_key,
        "Maine 10th pass kiya hai aur mere uncle ke saath lagbhag 2 saal "
        "ghar ki wiring aur switches repair karne ka kaam kiya. Hyderabad "
        "mein rehta hoon aur mujhe electrical field mein job chahiye.")
    print_report("TEST 1 — Hinglish", t1,
        "EXPECTED: education.level='10th', experience.duration_months=24, "
        "district='Hyderabad', state=null (NOT Telangana unless stated), "
        "employment_preference='job'.")

    # ── TEST 2: Very incomplete ───────────────────────────────────────────────
    t2 = run_test(model_path, api_key, "Mujhe electrician banna hai.")
    print_report("TEST 2 — Very Incomplete", t2,
        "EXPECTED: interests may contain 'electrical'. "
        "ALL other fields null/[]. No fabricated education/experience/location.")

    # ── TEST 3: Messy answer, unknown duration ───────────────────────────────
    t3 = run_test(model_path, api_key,
        "School 8th ke baad chhod diya tha. Abhi papa ke saath kabhi kabhi "
        "plumbing ka kaam karta hoon, pipes fitting thoda aata hai but exact "
        "kitne months ka experience hai pata nahi.")
    print_report("TEST 3 — Messy / Unknown Duration", t3,
        "EXPECTED: education.level='8th', education.status='dropped'. "
        "experience[0].domain='plumbing' or 'pipes fitting'. "
        "CRITICAL: experience[0].duration_months MUST be null — NOT invented.")

    # ── TEST 4: Multi-turn ───────────────────────────────────────────────────
    t4_1 = run_test(model_path, api_key, "Mujhe electrical kaam pasand hai.")
    print_report("TEST 4 — Turn 1", t4_1,
        "EXPECTED: interests=['electrical']. All else null/[].")

    t4_2 = run_test(model_path, api_key, "10th pass hoon.",
                    current_profile=t4_1["profile"])
    print_report("TEST 4 — Turn 2 (merged with Turn 1)", t4_2,
        "EXPECTED: interests PRESERVED=['electrical'], education.level='10th'.")

    t4_3 = run_test(model_path, api_key,
                    "About one and half year se wiring ka kaam kar raha hoon.",
                    current_profile=t4_2["profile"])
    print_report("TEST 4 — Turn 3 (merged with Turns 1+2)", t4_3,
        "EXPECTED: interests PRESERVED, education.level PRESERVED='10th', "
        "experience[0].domain='wiring' or 'electrical wiring', duration_months=18.")

    # ── TEST 5: No experience ─────────────────────────────────────────────────
    t5 = run_test(model_path, api_key,
        "I completed intermediate and I have never worked before. "
        "I want to learn computer hardware.")
    print_report("TEST 5 — No Experience Stated", t5,
        "EXPECTED: education.level='intermediate' or '12th'. "
        "experience=[] — MUST be empty. "
        "interests may contain 'computer hardware'. "
        "training_willingness=true.")

    print("\n" + "=" * 70)
    print("  ALL 5 TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
