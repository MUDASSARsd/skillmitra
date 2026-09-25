"""Online multilingual speech-to-text for SkillMitra.

Primary path: Gemini 3.5 Transcribe via one inline-audio Interactions API call.
Fallback path: Gemini Flash-Lite generateContent with the same inline WAV and a
strict transcription prompt. Short microphone clips do not use the Files API.

This module reads credentials only from the running process environment; it does
not open or modify .env files.
"""
from __future__ import annotations

import os
import re
import base64
from dataclasses import dataclass, asdict
from typing import Any

import requests


LANGUAGE_LOCALES = {
    "en": "en-IN",
    "hi": "hi-IN",
    "hinglish": "hi-IN",
    "te": "te-IN",
    "ta": "ta-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "mr": "mr-IN",
    "bn": "bn-IN",
    "gu": "gu-IN",
    "pa": "pa-IN",
    "or": "or-IN",
}

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "hinglish": "Hinglish (Hindi + English)",
    "te": "Telugu",
    "ta": "Tamil",
    "kn": "Kannada",
    "ml": "Malayalam",
    "mr": "Marathi",
    "bn": "Bengali",
    "gu": "Gujarati",
    "pa": "Punjabi",
    "or": "Odia",
}

# Bias toward the vocabulary that repeatedly appears in SkillMitra demos without
# forcing the model to invent any of these words.
CUSTOM_VOCABULARY = [
    "electrician", "electrical wiring", "electrician helper", "ITI",
    "NSQF", "NQR", "PM-AJAY", "Skill India", "Hyderabad", "Telangana",
    "mason", "plumber", "welder", "tailoring", "dairy farmer", "driver",
    "solar technician", "agriculture",
]


@dataclass
class OnlineSTTStatus:
    ready: bool
    engine: str = "gemini-3.5-transcribe"
    detail: str | None = None
    supported_languages: list[str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_error(value: str, secret: str | None) -> str:
    out = str(value or "")
    if secret:
        out = out.replace(secret, "<redacted>")
    out = re.sub(r"([?&]key=)[^&\s'\"]+", r"\1<redacted>", out, flags=re.I)
    return out[:500]


def _interaction_text(data: dict[str, Any]) -> str:
    text = data.get("output_text")
    if isinstance(text, str) and text.strip():
        return text.strip()

    # Be tolerant of interaction response variants by walking known content blocks.
    for step in reversed(data.get("steps") or []):
        for content in step.get("content") or []:
            if isinstance(content, dict):
                value = content.get("text")
                if isinstance(value, str) and value.strip():
                    return value.strip()
    for item in data.get("output") or data.get("outputs") or []:
        if isinstance(item, dict):
            value = item.get("text")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _generate_content_text(data: dict[str, Any]) -> str:
    try:
        parts = data["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError, TypeError):
        return ""
    return " ".join(
        str(p.get("text", "")).strip()
        for p in parts
        if isinstance(p, dict) and str(p.get("text", "")).strip()
    ).strip()


def _has_unexpected_arabic_script(text: str) -> bool:
    """Reject obvious wrong-script results for SkillMitra's UI languages.

    Urdu is not a selectable UI language. A few Arabic characters inside a URL or
    name are harmless, so only reject when Arabic-family codepoints dominate the
    alphabetic content.
    """
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return False
    arabic = sum(
        1 for ch in letters
        if ("\u0600" <= ch <= "\u06ff")
        or ("\u0750" <= ch <= "\u077f")
        or ("\u08a0" <= ch <= "\u08ff")
    )
    return arabic >= 3 and arabic / len(letters) >= 0.20


class OnlineSTT:
    def __init__(
        self,
        api_key: str | None = None,
        fallback_model: str | None = None,
        timeout: int = 18,
        session: Any | None = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.fallback_model = (fallback_model or os.getenv("SKILLMITRA_ONLINE_MODEL") or "gemini-3.5-flash-lite").strip()
        self.timeout = timeout
        self.session = session or requests

    def status(self) -> OnlineSTTStatus:
        ready = bool(self.api_key)
        return OnlineSTTStatus(
            ready=ready,
            detail=(
                "Online multilingual transcription is configured."
                if ready else
                "Online multilingual transcription needs the same Gemini API key used by Online AI mode."
            ),
            supported_languages=sorted(LANGUAGE_LOCALES),
        )

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("Online multilingual transcription is not configured.")
        return {"x-goog-api-key": self.api_key}

    def _upload_audio(self, audio: bytes, mime_type: str) -> tuple[str, str | None]:
        if not audio:
            raise ValueError("Audio recording is empty.")
        headers = {
            **self._headers(),
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(len(audio)),
            "X-Goog-Upload-Header-Content-Type": mime_type,
            "Content-Type": "application/json",
        }
        try:
            start = self.session.post(
                "https://generativelanguage.googleapis.com/upload/v1beta/files",
                headers=headers,
                json={"file": {"display_name": "skillmitra-microphone.wav"}},
                timeout=min(self.timeout, 10),
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Gemini audio upload failed: {_safe_error(str(exc), self.api_key)}") from None
        if not start.ok:
            raise RuntimeError(f"Gemini audio upload HTTP {start.status_code}: {_safe_error(start.text, self.api_key)}")
        upload_url = start.headers.get("x-goog-upload-url")
        if not upload_url:
            raise RuntimeError("Gemini audio upload did not return an upload URL.")

        try:
            finish = self.session.post(
                upload_url,
                headers={
                    "Content-Length": str(len(audio)),
                    "X-Goog-Upload-Offset": "0",
                    "X-Goog-Upload-Command": "upload, finalize",
                    "Content-Type": mime_type,
                },
                data=audio,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Gemini audio upload failed: {_safe_error(str(exc), self.api_key)}") from None
        if not finish.ok:
            raise RuntimeError(f"Gemini audio finalize HTTP {finish.status_code}: {_safe_error(finish.text, self.api_key)}")
        try:
            info = finish.json().get("file", {})
        except ValueError:
            info = {}
        uri = str(info.get("uri") or "").strip()
        name = str(info.get("name") or "").strip() or None
        if not uri:
            raise RuntimeError("Gemini audio upload completed but returned no file URI.")
        return uri, name

    def _delete_remote_file(self, name: str | None) -> None:
        if not name or not self.api_key:
            return
        try:
            self.session.delete(
                f"https://generativelanguage.googleapis.com/v1beta/{name}",
                headers=self._headers(),
                timeout=4,
            )
        except Exception:
            pass

    @staticmethod
    def _language_codes(language: str) -> list[str]:
        code = (language or "").lower().split("-")[0]
        locale = LANGUAGE_LOCALES.get(code)
        if not locale:
            return []
        if code in {"hi", "hinglish"}:
            return ["hi-IN", "en-IN"]
        if code == "en":
            return ["en-IN"]
        # Most beneficiary speech contains English occupation/course words.
        return [locale, "en-IN"]

    def _transcribe_dedicated_inline(self, audio: bytes, mime_type: str, language: str) -> str:
        payload = {
            "model": "gemini-3.5-transcribe",
            "input": [{
                "type": "audio",
                "data": base64.b64encode(audio).decode("ascii"),
                "mime_type": mime_type,
            }],
            "generation_config": {
                "transcription_config": {
                    "language_codes": self._language_codes(language),
                    "custom_vocabulary": CUSTOM_VOCABULARY,
                    "mode": {"type": "verbatim"},
                }
            },
        }
        try:
            response = self.session.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=min(self.timeout, 12),
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Gemini inline transcription failed: {_safe_error(str(exc), self.api_key)}") from None
        if not response.ok:
            raise RuntimeError(f"Gemini inline Transcribe HTTP {response.status_code}: {_safe_error(response.text, self.api_key)}")
        try:
            text = _interaction_text(response.json())
        except ValueError:
            text = ""
        if not text:
            raise RuntimeError("Gemini inline Transcribe returned an empty transcript.")
        return text

    def _transcribe_general_inline(self, audio: bytes, mime_type: str, language: str) -> str:
        code=(language or "en").lower().split("-")[0]
        label=LANGUAGE_NAMES.get(code, code)
        if code == "hinglish":
            script_instruction="Use Latin/Roman script for Hindi words and keep English words in English."
        elif code == "hi":
            script_instruction="Use Devanagari for Hindi and keep naturally spoken English terms in Latin script."
        elif code == "te":
            script_instruction="Use Telugu script for Telugu and keep naturally spoken English terms in Latin script. Never use Urdu/Arabic script."
        else:
            script_instruction=f"Use the normal native script for {label}; keep naturally spoken English terms in Latin script."
        prompt=(
            "Transcribe this beneficiary microphone recording faithfully. "
            f"Selected language: {label}. The speaker may code-switch with English or Hindi. "
            "Preserve numbers, experience duration, occupation names and place names. "
            "Do not translate, answer, summarize, or invent words. "
            f"{script_instruction} Return transcript text only."
        )
        payload={
            "contents":[{"parts":[
                {"text":prompt},
                {"inline_data":{"mime_type":mime_type,"data":base64.b64encode(audio).decode("ascii")}},
            ]}],
            "generationConfig":{
                "maxOutputTokens":160,
                "thinkingConfig":{"thinkingLevel":"minimal"},
            },
        }
        try:
            response=self.session.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.fallback_model}:generateContent",
                headers={**self._headers(), "Content-Type":"application/json"},
                json=payload, timeout=min(self.timeout,12),
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Gemini inline audio fallback failed: {_safe_error(str(exc), self.api_key)}") from None
        if not response.ok:
            raise RuntimeError(f"Gemini inline audio fallback HTTP {response.status_code}: {_safe_error(response.text, self.api_key)}")
        try:
            text=_generate_content_text(response.json())
        except ValueError:
            text=""
        if not text:
            raise RuntimeError("Gemini inline audio fallback returned an empty transcript.")
        return text

    def _transcribe_dedicated(self, uri: str, mime_type: str, language: str) -> str:
        payload = {
            "model": "gemini-3.5-transcribe",
            "input": [{"type": "audio", "uri": uri, "mime_type": mime_type}],
            "generation_config": {
                "transcription_config": {
                    "language_codes": self._language_codes(language),
                    "custom_vocabulary": CUSTOM_VOCABULARY,
                    "mode": {"type": "verbatim"},
                }
            },
        }
        try:
            response = self.session.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Gemini transcription failed: {_safe_error(str(exc), self.api_key)}") from None
        if not response.ok:
            raise RuntimeError(f"Gemini Transcribe HTTP {response.status_code}: {_safe_error(response.text, self.api_key)}")
        try:
            text = _interaction_text(response.json())
        except ValueError:
            text = ""
        if not text:
            raise RuntimeError("Gemini Transcribe returned an empty transcript.")
        return text

    def _transcribe_general_model(self, uri: str, mime_type: str, language: str) -> str:
        model = self.fallback_model
        if not model:
            raise RuntimeError("No general Gemini model is available as a transcription fallback.")
        code = (language or "en").lower().split("-")[0]
        label = LANGUAGE_NAMES.get(code, code)
        if code == "hinglish":
            script_instruction = "Use Latin/Roman script for the Hindi words and keep English words in English."
        elif code == "hi":
            script_instruction = "Use Devanagari for Hindi and keep naturally spoken English terms in Latin script."
        elif code == "te":
            script_instruction = "Use Telugu script for Telugu and keep naturally spoken English terms in Latin script. Never use Urdu/Arabic script."
        else:
            script_instruction = f"Use the normal native script for {label}; keep naturally spoken English terms in Latin script."
        prompt = (
            "Transcribe this beneficiary microphone recording faithfully. "
            f"Selected language: {label}. The speaker may code-switch with English or Hindi. "
            "Preserve the actual numbers, years of experience, occupation names and place names. "
            "Do not translate, answer, summarize, or invent missing words. "
            f"{script_instruction} Return transcript text only."
        )
        payload = {
            "contents": [{"parts": [
                {"text": prompt},
                {"file_data": {"mime_type": mime_type, "file_uri": uri}},
            ]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": 256},
        }
        try:
            response = self.session.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={**self._headers(), "Content-Type": "application/json"},
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Gemini audio fallback failed: {_safe_error(str(exc), self.api_key)}") from None
        if not response.ok:
            raise RuntimeError(f"Gemini audio fallback HTTP {response.status_code}: {_safe_error(response.text, self.api_key)}")
        try:
            text = _generate_content_text(response.json())
        except ValueError:
            text = ""
        if not text:
            raise RuntimeError("Gemini audio fallback returned an empty transcript.")
        return text

    def transcribe(self, audio: bytes, language: str = "en", mime_type: str = "audio/wav") -> tuple[str, str]:
        if not self.api_key:
            raise RuntimeError("Online multilingual transcription is not configured.")
        if len(audio) > 20 * 1024 * 1024:
            raise ValueError("Audio recording is too large for voice transcription.")

        errors=[]
        # Jury fast path: microphone clips are tiny, so send audio inline in ONE
        # request. Earlier builds uploaded + finalized + transcribed + deleted the file,
        # adding several avoidable network round trips.
        try:
            text=self._transcribe_dedicated_inline(audio, mime_type, language)
            if _has_unexpected_arabic_script(text):
                raise RuntimeError("transcript used an unrelated Arabic/Urdu script")
            return text.strip(), "gemini-3.5-transcribe-inline"
        except RuntimeError as exc:
            errors.append(str(exc))

        try:
            text=self._transcribe_general_inline(audio, mime_type, language)
            if _has_unexpected_arabic_script(text):
                raise RuntimeError("fallback transcript used an unrelated Arabic/Urdu script")
            return text.strip(), "gemini-flash-lite-inline"
        except RuntimeError as exc:
            errors.append(str(exc))

        raise RuntimeError("; ".join(errors) or "Online multilingual transcription failed.")

