"""Free-form multilingual offline profile extraction through a local Ollama LLM.

The LLM is used only for language understanding / entity extraction. Course
selection, eligibility, ranking and recommendations remain deterministic.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Optional

import requests

from backend.models.beneficiary import BeneficiaryProfile
from backend.nlu.base import ProfileExtractor
from backend.nlu.local_extractor import LocalProfileExtractor


EXTRACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "education": {
            "type": "object",
            "properties": {
                "level": {"type": ["string", "null"]},
                "status": {"type": ["string", "null"]},
                "stream": {"type": ["string", "null"]},
            },
            "required": ["level", "status", "stream"],
        },
        "occupation": {"type": ["string", "null"]},
        "skills": {"type": "array", "items": {"type": "string"}},
        "interests": {"type": "array", "items": {"type": "string"}},
        "experience": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "domain": {"type": ["string", "null"]},
                    "duration_months": {"type": ["integer", "null"]},
                },
                "required": ["domain", "duration_months"],
            },
        },
        "location": {
            "type": "object",
            "properties": {
                "state": {"type": ["string", "null"]},
                "district": {"type": ["string", "null"]},
            },
            "required": ["state", "district"],
        },
        "employment_preference": {"type": ["string", "null"]},
        "training_willingness": {"type": ["boolean", "null"]},
        "mobility_km": {"type": ["integer", "null"]},
        "language": {"type": ["string", "null"]},
    },
    "required": [
        "education", "occupation", "skills", "interests", "experience",
        "location", "employment_preference", "training_willingness",
        "mobility_km", "language",
    ],
}

SYSTEM_PROMPT = """You are SkillMitra's multilingual beneficiary-profile extractor. Understand natural English, Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi, Odia, Hinglish and code-mixed speech, imperfect grammar, and minor ASR errors by meaning, not by exact phrase matching.
Return ONLY JSON matching the supplied schema. Extract only facts stated in THIS user turn; the current profile is context, not new evidence.

FIELD DISCIPLINE:
- education: only schooling/qualification facts. Preserve passed vs dropout/not-completed correctly.
- occupation: the person's actual/current work, in concise canonical English. Preserve the real meaning; never replace it with a different occupation because words sound similar.
- skills: only abilities/trades the person says they know or do.
- interests: only work/career interests; NEVER put a city, district, state, education fact, or duration here.
- experience: if the user says they did/helped/worked in a kind of work for a duration, capture domain + duration_months. Convert years to months correctly (1 year=12, 1.5 years=18, 2 years=24). If the user explicitly says they have no work experience, return one experience record with domain=null and duration_months=0 so the system knows the question was answered.
- location: only place of residence/area/district/state.
- employment_preference: job, self_employment, or business only when supported.
- training_willingness: set only when the user explicitly answers willingness, especially when QUESTION_TOPIC=training_willingness. Otherwise null.

CONTEXTUAL REPLIES:
Use QUESTION_TOPIC to understand short replies such as yes/no, a place name, a qualification, or a duration. If QUESTION_TOPIC=training_willingness, decide whether the reply means willing/yes, unwilling/no, or unclear and set true/false/null.

SEMANTIC ACCURACY:
Preserve the user's occupation meaning. Construction/building work is not housekeeping/cleaning; electrical work is not electronics retail; similar-looking words are not evidence. If ASR text is imperfect, prefer the interpretation that best fits the full sentence and current question. Do not invent facts. Do not recommend courses here."""


def _next_missing_field(profile: Optional[BeneficiaryProfile]) -> Optional[str]:
    if profile is None:
        return None
    if not profile.education.level:
        return "education"
    if not (profile.interests or profile.skills or profile.occupation):
        return "livelihood_signal"
    if not profile.experience:
        return "experience"
    if profile.employment_preference is None:
        return "employment_preference"
    if not (profile.location.district or profile.location.state):
        return "location"
    if profile.training_willingness is None:
        return "training_willingness"
    return None


def _blank_payload() -> Dict[str, Any]:
    return {
        "education": {"level": None, "status": None, "stream": None},
        "occupation": None,
        "skills": [],
        "interests": [],
        "experience": [],
        "location": {"state": None, "district": None},
        "employment_preference": None,
        "training_willingness": None,
        "mobility_km": None,
        "language": None,
    }


def _clean_json(raw: str) -> str:
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\\s*", "", s, flags=re.I)
    s = re.sub(r"\\s*```$", "", s)
    return s.strip()


def _coerce_payload(value: Dict[str, Any]) -> Dict[str, Any]:
    """Make minor model-output shape variations safe for Pydantic validation."""
    out = _blank_payload()

    edu = value.get("education")
    if isinstance(edu, str):
        out["education"]["level"] = edu
    elif isinstance(edu, dict):
        for k in ("level", "status", "stream"):
            if edu.get(k) is not None:
                out["education"][k] = edu.get(k)

    for k in ("occupation", "employment_preference", "training_willingness", "mobility_km", "language"):
        if k in value:
            out[k] = value.get(k)

    for k in ("skills", "interests"):
        v = value.get(k)
        if isinstance(v, str):
            out[k] = [v]
        elif isinstance(v, list):
            out[k] = [str(x) for x in v if x is not None and str(x).strip()]

    loc = value.get("location")
    if isinstance(loc, str):
        out["location"]["district"] = loc
    elif isinstance(loc, dict):
        out["location"]["state"] = loc.get("state")
        out["location"]["district"] = loc.get("district")

    exp = value.get("experience")
    if isinstance(exp, dict):
        exp = [exp]
    if isinstance(exp, list):
        normalized = []
        for item in exp:
            if isinstance(item, dict):
                normalized.append({
                    "domain": item.get("domain"),
                    "duration_months": item.get("duration_months"),
                })
        out["experience"] = normalized

    # Canonicalise a few semantic values after the model has understood them.
    pref = out.get("employment_preference")
    if isinstance(pref, str):
        p = pref.strip().lower().replace("-", "_").replace(" ", "_")
        if "business" in p or "own_business" in p or "start_own" in p:
            out["employment_preference"] = "business"
        elif "self" in p and ("employ" in p or "work" in p):
            out["employment_preference"] = "self_employment"
        elif "job" in p or "employment" == p:
            out["employment_preference"] = "job"

    level = out["education"].get("level")
    if isinstance(level, str):
        low = level.lower().strip()
        if re.search(r"(?:^|\b)(10th|10|tenth)(?:\b|$)", low):
            out["education"]["level"] = "10th"
        elif re.search(r"(?:^|\b)(12th|12|twelfth|intermediate)(?:\b|$)", low):
            out["education"]["level"] = "12th"
        elif "diploma" in low:
            out["education"]["level"] = "Diploma"

    return out


def _compact_profile(profile: Optional[BeneficiaryProfile]) -> Dict[str, Any]:
    """Send only known profile facts to the local LLM to reduce prompt tokens/latency."""
    if profile is None:
        return {}
    raw = profile.model_dump()

    def prune(value):
        if isinstance(value, dict):
            out = {k: prune(v) for k, v in value.items()}
            return {k: v for k, v in out.items() if v not in (None, [], {}, "")}
        if isinstance(value, list):
            vals = [prune(v) for v in value]
            return [v for v in vals if v not in (None, [], {}, "")]
        return value

    return prune(raw)


def _canonical_education(payload: Dict[str, Any]) -> None:
    """Normalize model shape mistakes without trying to understand the user's language."""
    edu = payload.get("education") or {}
    level = edu.get("level")
    status = edu.get("status")
    if isinstance(level, str):
        low = level.strip().lower().replace("_", "-")
        # A status accidentally placed in level should never become a qualification.
        if low in {"dropout", "dropped-out", "not-completed", "not completed", "incomplete", "passed", "completed"}:
            if not status:
                edu["status"] = "dropout" if "drop" in low or "not" in low or "incomplete" in low else "passed"
            edu["level"] = None
    if isinstance(edu.get("status"), str):
        st = edu["status"].strip().lower().replace("_", "-")
        if st in {"dropout", "dropped-out", "not-completed", "not completed", "incomplete"}:
            edu["status"] = "dropout"
        elif st in {"passed", "completed", "complete"}:
            edu["status"] = "passed"
    payload["education"] = edu


def _focus_guard(payload: Dict[str, Any], expected: Optional[str]) -> Dict[str, Any]:
    """Prevent a short follow-up answer from corrupting unrelated profile fields.

    This is field-level conversation control, not phrase matching. The LLM still
    understands the natural-language answer; we only restrict which schema fields
    are allowed to change when SkillMitra asked a focused question.
    """
    if not expected:
        return payload
    allowed = {
        "education": {"education", "language"},
        "location": {"location", "language"},
        "training_willingness": {"training_willingness", "language"},
        "employment_preference": {"employment_preference", "language"},
        "experience": {"experience", "occupation", "skills", "language"},
        "livelihood_signal": {"occupation", "skills", "interests", "experience", "employment_preference", "language"},
    }.get(expected)
    if not allowed:
        return payload
    blank = _blank_payload()
    for key in allowed:
        if key in payload:
            blank[key] = payload[key]
    return blank


def _cross_field_sanity(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Remove obvious schema leakage across location/interest/skill fields."""
    loc = payload.get("location") or {}
    places = {str(v).strip().casefold() for v in (loc.get("state"), loc.get("district")) if v}
    if places:
        for key in ("skills", "interests"):
            vals = payload.get(key) or []
            payload[key] = [v for v in vals if str(v).strip().casefold() not in places]
    _canonical_education(payload)
    return payload


class OllamaProfileExtractor(ProfileExtractor):
    """Primary offline free-form extractor backed by a local Ollama model."""

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 90,
        fallback: Optional[ProfileExtractor] = None,
        request_post=None,
    ):
        self.model = model or os.getenv("OLLAMA_MODEL", "gemma3:4b")
        self.fast_model = os.getenv("OLLAMA_FAST_MODEL", "gemma3:1b").strip()
        self.prefer_fast = os.getenv("OLLAMA_PREFER_FAST", "1").strip().lower() in {"1", "true", "yes"}
        self._selected_model = None
        self.last_model_used = None
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")).rstrip("/")
        self.timeout = timeout
        self.fallback = fallback
        self._post = request_post or requests.post

    def _choose_model(self) -> str:
        if self._selected_model:
            return self._selected_model
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models", [])]
            if self.prefer_fast and self.fast_model and self.fast_model in names:
                self._selected_model = self.fast_model
            elif self.model in names:
                self._selected_model = self.model
            else:
                self._selected_model = self.model
        except Exception:
            self._selected_model = self.model
        return self._selected_model

    def status(self) -> Dict[str, Any]:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            if not r.ok:
                return {"ready": False, "model": self.model, "detail": f"Ollama HTTP {r.status_code}"}
            names = [m.get("name", "") for m in r.json().get("models", [])]
            model_ready = any(n == self.model or n.startswith(self.model + ":") for n in names)
            # Ollama often returns exact tag e.g. gemma3:4b; keep an explicit check.
            model_ready = model_ready or self.model in names
            fast_ready = bool(self.fast_model and self.fast_model in names)
            selected = self.fast_model if (self.prefer_fast and fast_ready) else self.model
            selected_ready = selected in names
            self._selected_model = selected if selected_ready else self.model
            return {
                "ready": selected_ready or model_ready,
                "server_ready": True,
                "model": self._selected_model,
                "quality_model": self.model,
                "fast_model": self.fast_model,
                "fast_model_ready": fast_ready,
                "installed_models": names,
                "detail": (f"Local multilingual LLM ready: {self._selected_model}." if (selected_ready or model_ready)
                           else f"Ollama is running but {self.model} is not installed."),
            }
        except Exception as exc:
            return {"ready": False, "server_ready": False, "model": self.model, "detail": f"Ollama unavailable: {exc}"}

    def warmup(self) -> bool:
        """Load the selected model into memory using the same chat API used for extraction."""
        try:
            payload = {
                "model": self._choose_model(),
                "stream": False,
                "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
                "options": {"num_predict": 1},
                "messages": [{"role": "user", "content": "Return {}"}],
            }
            r = self._post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
            if not r.ok:
                raise RuntimeError(f"Ollama warmup HTTP {r.status_code}: {r.text[:300]}")
            return True
        except Exception:
            return False

    def _call_with_model(self, model_name: str, prompt: str) -> str:
        self.last_model_used = model_name
        payload = {
            "model": model_name,
            "stream": False,
            "format": EXTRACTION_SCHEMA,
            "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
            "options": {
                "temperature": 0,
                "num_predict": int(os.getenv("OLLAMA_NUM_PREDICT", "128")),
                "num_ctx": int(os.getenv("OLLAMA_NUM_CTX", "1536")),
            },
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
        r = self._post(f"{self.base_url}/api/chat", json=payload, timeout=self.timeout)
        if not r.ok:
            raise RuntimeError(f"Ollama HTTP {r.status_code} using {model_name}: {r.text[:500]}")
        body = r.json()
        return body.get("message", {}).get("content", "") or body.get("response", "")

    def _call(self, user_text: str, current_profile: Optional[BeneficiaryProfile], language_code: Optional[str]) -> str:
        profile_json = json.dumps(_compact_profile(current_profile), ensure_ascii=False, separators=(",", ":"))
        expected = _next_missing_field(current_profile)
        prompt = (
            f"PROFILE={profile_json}\n"
            f"QUESTION_TOPIC={expected or 'open_profile_introduction'}\n"
            f"LANG={language_code or 'unknown'}\n"
            f"USER={user_text}\nJSON="
        )
        # Accuracy-first routing: use the 4B quality model for open/complex turns,
        # and the 1B model only for focused, simple follow-ups. This keeps free-form
        # understanding while avoiding the semantic drift seen when 1B handled everything.
        installed_choice = self._choose_model()
        simple_topics = {"education", "location", "training_willingness", "employment_preference"}
        selected = installed_choice if expected in simple_topics else self.model
        try:
            return self._call_with_model(selected, prompt)
        except Exception:
            if selected != self.model:
                return self._call_with_model(self.model, prompt)
            raise

    def _classify_training_reply(self, user_text: str, language_code: Optional[str]) -> Optional[bool]:
        """Tiny semantic follow-up classifier used only when the main extraction missed a training yes/no reply.

        This remains free-form multilingual NLU: no phrase lists or regex keyword matching.
        """
        schema = {
            "type": "object",
            "properties": {"answer": {"type": "string", "enum": ["yes", "no", "unknown"]}},
            "required": ["answer"],
        }
        payload = {
            "model": self._choose_model(),
            "stream": False,
            "format": schema,
            "keep_alive": os.getenv("OLLAMA_KEEP_ALIVE", "30m"),
            "options": {"temperature": 0, "num_predict": 12, "num_ctx": 512},
            "messages": [
                {"role": "system", "content": "Classify whether the user's reply means YES/willing, NO/not willing, or UNKNOWN in the context: Would you take a course or training if it helps your work goal? Understand English, Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi, Odia and mixed language. Return JSON only."},
                {"role": "user", "content": f"LANG={language_code or 'unknown'}\nUSER={user_text}"},
            ],
        }
        try:
            r = self._post(f"{self.base_url}/api/chat", json=payload, timeout=min(self.timeout, 30))
            if not r.ok:
                return None
            raw = r.json().get("message", {}).get("content", "")
            answer = json.loads(_clean_json(raw)).get("answer")
            if answer == "yes": return True
            if answer == "no": return False
        except Exception:
            return None
        return None

    def extract(self, text: str, current_profile: Optional[BeneficiaryProfile] = None,
                language_code: Optional[str] = None) -> BeneficiaryProfile:
        if not text or not text.strip():
            return current_profile if current_profile else BeneficiaryProfile(language=language_code)
        try:
            raw = self._call(text.strip(), current_profile, language_code)
            try:
                parsed = json.loads(_clean_json(raw))
                if not isinstance(parsed, dict):
                    raise ValueError("Ollama returned a non-object JSON response")
                data = _coerce_payload(parsed)
                expected = _next_missing_field(current_profile)
                data = _focus_guard(data, expected)
                data = _cross_field_sanity(data)
                extracted = BeneficiaryProfile.model_validate(data)
            except Exception:
                # If the selected fast model produced malformed/invalid JSON, retry the same
                # free-form extraction with the quality model. This is not a rule-based fallback.
                if self._choose_model() != self.model:
                    profile_json = json.dumps(_compact_profile(current_profile), ensure_ascii=False, separators=(",", ":"))
                    expected = _next_missing_field(current_profile)
                    prompt = (f"PROFILE={profile_json}\n"
                              f"QUESTION_TOPIC={expected or 'open_profile_introduction'}\n"
                              f"LANG={language_code or 'unknown'}\n"
                              f"USER={text.strip()}\nJSON=")
                    raw = self._call_with_model(self.model, prompt)
                    parsed = json.loads(_clean_json(raw))
                    data = _coerce_payload(parsed)
                    expected = _next_missing_field(current_profile)
                    data = _focus_guard(data, expected)
                    data = _cross_field_sanity(data)
                    extracted = BeneficiaryProfile.model_validate(data)
                else:
                    raise
            if language_code and not extracted.language:
                extracted.language = language_code

            # If a short free-form answer to the training question was missed, use a
            # dedicated semantic classifier instead of hard-coded yes/no phrases.
            expected = _next_missing_field(current_profile)
            if expected == "training_willingness" and extracted.training_willingness is None:
                classified = self._classify_training_reply(text.strip(), language_code)
                if classified is not None:
                    extracted.training_willingness = classified

            return current_profile.merge(extracted) if current_profile else extracted
        except Exception:
            if self.fallback is not None:
                return self.fallback.extract(text, current_profile, language_code)
            raise


class HybridOfflineProfileExtractor(OllamaProfileExtractor):
    """Fast deterministic-first offline extractor with Ollama for genuinely hard text.

    Jury answers such as education, electrician experience, location, job/business and
    training willingness should return immediately instead of paying an LLM latency cost.
    Unknown/complex livelihood descriptions still fall through to local Ollama.
    """

    def __init__(self, **kwargs):
        # The deterministic extractor is a safety net, not an optional feature.
        # Offline text/NQR recommendations must keep working even when Ollama is
        # absent, stopped, or a stale local setting says otherwise.  Callers can
        # still explicitly pass a different fallback for tests/advanced use.
        if "fallback" not in kwargs:
            kwargs["fallback"] = LocalProfileExtractor()
        super().__init__(**kwargs)

    @staticmethod
    def _profile_signature(profile):
        if profile is None:
            return None
        return (
            profile.education.level, profile.education.status,
            profile.occupation, tuple(profile.skills or []), tuple(profile.interests or []),
            tuple((x.domain, x.duration_months) for x in (profile.experience or [])),
            profile.location.state, profile.location.district,
            profile.employment_preference, profile.training_willingness, profile.mobility_km,
        )

    @staticmethod
    def _patch_has_substantive_fact(patch):
        if patch is None:
            return False
        return bool(
            patch.education.level or patch.education.status or patch.education.stream
            or patch.occupation or patch.skills or patch.interests or patch.experience
            or patch.location.state or patch.location.district
            or patch.employment_preference is not None
            or patch.training_willingness is not None
            or patch.mobility_km is not None
        )

    def extract(self, text, current_profile=None, language_code=None):
        clean = (text or "").strip()
        if self.fallback is not None:
            if hasattr(self.fallback, "extract_patch"):
                patch = self.fallback.extract_patch(clean, current_profile, language_code)
                fast = patch if current_profile is None else current_profile.model_copy(deep=True).merge(patch)
                recognized = self._patch_has_substantive_fact(patch)
            else:
                fast = self.fallback.extract(clean, current_profile, language_code)
                recognized = self._profile_signature(fast) != self._profile_signature(current_profile)
            changed = self._profile_signature(fast) != self._profile_signature(current_profile)
            # Understood/duplicate facts and short counter-question replies stay fast.
            # Ollama is reserved for genuinely hard free-form text, never required
            # for the core offline conversation.
            if changed or recognized or len(clean.split()) <= 6:
                self.last_model_used = "rules-fastpath"
                return fast
        try:
            return super().extract(clean, current_profile, language_code)
        except Exception:
            # Defense-in-depth: even an explicit/custom Ollama failure must not turn
            # the offline beneficiary API into a 503 when deterministic parsing works.
            if self.fallback is not None:
                self.last_model_used = "rules-fallback"
                return self.fallback.extract(clean, current_profile, language_code)
            raise
