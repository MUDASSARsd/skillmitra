"""Online multilingual text-to-speech fallback using edge-tts.

This module is intentionally independent from the project's .env.  It is used
only in Online AI mode when the browser/OS does not expose a matching native
speech-synthesis voice.
"""
from __future__ import annotations

import importlib.util
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


ONLINE_VOICES = {
    "en": "en-IN-NeerjaNeural",
    "hi": "hi-IN-SwaraNeural",
    "hinglish": "hi-IN-SwaraNeural",
    "te": "te-IN-ShrutiNeural",
    "ta": "ta-IN-PallaviNeural",
    "kn": "kn-IN-SapnaNeural",
    "ml": "ml-IN-SobhanaNeural",
    "mr": "mr-IN-AarohiNeural",
    "bn": "bn-IN-TanishaaNeural",
    "gu": "gu-IN-DhwaniNeural",
    "pa": "pa-IN-VaaniNeural",
    "or": "or-IN-SubhasiniNeural",
}


@dataclass
class OnlineTTSStatus:
    ready: bool
    engine: str = "edge-tts"
    supported_languages: list[str] | None = None
    detail: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class OnlineTTS:
    @staticmethod
    def _installed() -> bool:
        return importlib.util.find_spec("edge_tts") is not None

    def status(self) -> OnlineTTSStatus:
        ready = self._installed()
        return OnlineTTSStatus(
            ready=ready,
            supported_languages=sorted(ONLINE_VOICES),
            detail=(
                "Online multilingual TTS ready."
                if ready
                else "edge-tts is not installed. Run UPDATE_VOICE_SUPPORT.bat once."
            ),
        )

    async def synthesize(self, text: str, language: str) -> Path:
        if not self._installed():
            raise RuntimeError("Online multilingual TTS is not installed. Run UPDATE_VOICE_SUPPORT.bat once.")
        lang = (language or "en").lower().replace("_", "-").split("-")[0]
        voice = ONLINE_VOICES.get(lang)
        if not voice:
            raise RuntimeError(f"Online TTS does not have a configured voice for {language}.")
        if not text.strip():
            raise ValueError("Text is empty.")

        import edge_tts

        fd, name = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        out = Path(name)
        try:
            communicate = edge_tts.Communicate(text=text, voice=voice)
            await communicate.save(str(out))
            if not out.is_file() or out.stat().st_size == 0:
                raise RuntimeError("Online TTS returned empty audio.")
            return out
        except Exception:
            out.unlink(missing_ok=True)
            raise
