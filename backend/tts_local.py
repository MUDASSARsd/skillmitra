"""Offline multilingual text-to-speech.

Engine priority:
1. Piper for Hindi/Telugu when the configured project-local voice exists.
2. eSpeak NG as a compact fully-offline fallback for all UI languages.

No .env file is required or modified by this module. Environment variables for
legacy Piper overrides remain supported for backward compatibility only.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import tempfile
import threading
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

_VOICE_CACHE = {}
_ROOT = Path(__file__).resolve().parents[1]

# High-quality optional Piper voices already used by the project.
_PIPER_VOICES = {
    "en": {
        "name": "en_US-lessac-medium.onnx",
        "folder": "piper-en",
        "model_env": "PIPER_ENGLISH_MODEL",
        "config_env": "PIPER_ENGLISH_CONFIG",
        "dir_env": "PIPER_ENGLISH_DIR",
        "label": "English",
    },
    "te": {
        "name": "te_IN-padmavathi-medium.onnx",
        "folder": "piper-te",
        "model_env": "PIPER_TELUGU_MODEL",
        "config_env": "PIPER_TELUGU_CONFIG",
        "dir_env": "PIPER_TELUGU_DIR",
        "label": "Telugu",
    },
    "hi": {
        "name": "hi_IN-pratham-medium.onnx",
        "folder": "piper-hi",
        "model_env": "PIPER_HINDI_MODEL",
        "config_env": "PIPER_HINDI_CONFIG",
        "dir_env": "PIPER_HINDI_DIR",
        "label": "Hindi",
    },
}

# eSpeak NG uses BCP-47-ish language identifiers and supports these languages
# locally. "hinglish" intentionally uses the Hindi voice so Devanagari/Hindi
# content is handled consistently while English loanwords remain intelligible.
_ESPEAK_VOICES = {
    "en": "en",
    "hi": "hi",
    "hinglish": "hi",
    "te": "te",
    "ta": "ta",
    "kn": "kn",
    "ml": "ml",
    "mr": "mr",
    "bn": "bn",
    "gu": "gu",
    "pa": "pa",
    "or": "or",
}

_LABELS = {
    "en": "English",
    "hi": "Hindi",
    "hinglish": "Hinglish",
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


@dataclass
class LocalTTSStatus:
    ready: bool
    telugu_ready: bool = False
    hindi_ready: bool = False
    espeak_ready: bool = False
    detail: str | None = None
    telugu_model: str | None = None
    telugu_config: str | None = None
    hindi_model: str | None = None
    hindi_config: str | None = None
    espeak_executable: str | None = None
    espeak_data_parent: str | None = None
    supported_languages: list[str] | None = None
    languages: dict | None = None
    discovery: dict | None = None

    def as_dict(self):
        return asdict(self)


class LocalTTS:
    def __init__(self):
        self._voices = {lang: self._discover_voice(lang) for lang in _PIPER_VOICES}
        self.telugu_model, self.telugu_config, self.telugu_discovery = self._voices["te"]
        self.hindi_model, self.hindi_config, self.hindi_discovery = self._voices["hi"]
        # Kept for backward-compatible tests/code that used the old Telugu-only field.
        self.discovery = self.telugu_discovery
        self.espeak_executable = self._discover_espeak_ng()
        self.espeak_data_parent = self._discover_espeak_data_parent(self.espeak_executable)

    @staticmethod
    def _candidate_pair(model: Path, config: Path | None = None):
        config = config or Path(str(model) + ".json")
        return model.expanduser(), config.expanduser()

    def _discover_voice(self, lang: str):
        spec = _PIPER_VOICES[lang]
        allow_external = os.getenv("ALLOW_EXTERNAL_MODEL_PATHS", "0").strip().lower() in {"1", "true", "yes"}
        env_model = os.getenv(spec["model_env"], "").strip().strip('"') if allow_external else ""
        env_config = os.getenv(spec["config_env"], "").strip().strip('"') if allow_external else ""
        if env_model:
            model, config = self._candidate_pair(Path(env_model), Path(env_config) if env_config else None)
            return model, config, "external-environment"

        env_dir = os.getenv(spec["dir_env"], "").strip().strip('"') if allow_external else ""
        candidates: list[tuple[Path, str]] = []
        if env_dir:
            candidates.append((Path(env_dir) / spec["name"], spec["dir_env"]))

        candidates.extend([
            (_ROOT / "models" / spec["folder"] / spec["name"], "project-local"),
            (_ROOT / "models" / "piper" / spec["name"], "project-local"),
        ])

        for model, source in candidates:
            model, config = self._candidate_pair(model)
            if model.is_file() and config.is_file():
                return model, config, source

        model, config = self._candidate_pair(candidates[0][0])
        return model, config, "not-found"

    @staticmethod
    def _discover_espeak_ng() -> Path | None:
        """Find eSpeak NG without relying on .env or requiring a shell restart."""
        on_path = shutil.which("espeak-ng")
        if on_path:
            p = Path(on_path)
            if p.is_file():
                return p

        project_root = _ROOT / "tools" / "espeak-ng"
        candidates: list[Path] = [
            project_root / "espeak-ng.exe",
        ]
        if project_root.is_dir():
            candidates.extend(project_root.rglob("espeak-ng.exe"))
        candidates.extend([
            Path(r"C:\Program Files\eSpeak NG\espeak-ng.exe"),
            Path(r"C:\Program Files (x86)\eSpeak NG\espeak-ng.exe"),
        ])
        for p in candidates:
            if p.is_file():
                return p
        return None

    @staticmethod
    def _discover_espeak_data_parent(exe: Path | None) -> Path | None:
        """Find the directory that *contains* espeak-ng-data.

        The Windows CLI accepts --path=<parent>. Project-local MSI extraction
        does not create the normal registry key, so passing this explicitly is
        required for reliable portable TTS.
        """
        roots: list[Path] = []
        if exe:
            roots.extend([exe.parent, exe.parent.parent, exe.parent / "share", exe.parent.parent / "share"])
        roots.extend([_ROOT / "tools" / "espeak-ng", _ROOT / "tools" / "espeak-ng" / "package"])
        seen: set[str] = set()
        for root in roots:
            try:
                key = str(root.resolve())
            except Exception:
                key = str(root)
            if key in seen or not root.exists():
                continue
            seen.add(key)
            direct = root / "espeak-ng-data"
            if direct.is_dir():
                return root
            try:
                for d in root.rglob("espeak-ng-data"):
                    if d.is_dir():
                        return d.parent
            except Exception:
                pass
        return None

    @staticmethod
    def _piper_installed():
        return importlib.util.find_spec("piper") is not None

    def _piper_ready(self, lang: str):
        if lang not in _PIPER_VOICES:
            return False
        model, config, _ = self._voices[lang]
        return bool(
            self._piper_installed()
            and model
            and model.is_file()
            and config
            and config.is_file()
        )

    def _espeak_ready(self):
        return bool(self.espeak_executable and self.espeak_executable.is_file())

    # Backward-compatible name used by earlier tests.
    def _voice_ready(self, lang: str):
        return self._piper_ready(lang)

    @staticmethod
    def _normalize_language(language: str) -> str:
        raw = (language or "en").lower().replace("_", "-")
        if raw == "hinglish":
            return "hinglish"
        return raw.split("-")[0]

    def status(self):
        te_piper = self._piper_ready("te")
        hi_piper = self._piper_ready("hi")
        espeak = self._espeak_ready()

        languages = {}
        for lang in _ESPEAK_VOICES:
            piper_ready = self._piper_ready(lang)
            ready = piper_ready or espeak
            engine = "piper" if piper_ready else ("espeak-ng" if espeak else None)
            languages[lang] = {
                "ready": ready,
                "engine": engine,
                "label": _LABELS.get(lang, lang),
            }

        if espeak:
            detail = (
                "Offline multilingual TTS ready. Piper is preferred for installed Hindi/Telugu voices; "
                "eSpeak NG provides the local fallback for all supported languages."
            )
        elif te_piper or hi_piper:
            missing_piper = []
            if not te_piper:
                missing_piper.append("SETUP_TELUGU_TTS.bat")
            if not hi_piper:
                missing_piper.append("SETUP_HINDI_TTS.bat")
            detail = (
                "Offline TTS is partially ready. Hindi/Telugu Piper may work, but multilingual fallback is missing. "
                "Run SETUP_OFFLINE_TTS.bat once."
            )
            if missing_piper:
                detail += " Optional higher-quality voice setup: " + " and ".join(missing_piper) + "."
        else:
            # Keep the old actionable Telugu setup phrase for compatibility while
            # directing new installs to the one multilingual setup step.
            detail = (
                "No local TTS engine is ready. Run SETUP_OFFLINE_TTS.bat once for multilingual offline speech. "
                "Optional higher-quality voices: SETUP_HINDI_TTS.bat and SETUP_TELUGU_TTS.bat."
            )

        return LocalTTSStatus(
            ready=any(v["ready"] for v in languages.values()),
            telugu_ready=languages["te"]["ready"],
            hindi_ready=languages["hi"]["ready"],
            espeak_ready=espeak,
            detail=detail,
            telugu_model=str(self.telugu_model),
            telugu_config=str(self.telugu_config),
            hindi_model=str(self.hindi_model),
            hindi_config=str(self.hindi_config),
            espeak_executable=str(self.espeak_executable) if self.espeak_executable else None,
            espeak_data_parent=str(self.espeak_data_parent) if self.espeak_data_parent else None,
            supported_languages=sorted(_ESPEAK_VOICES),
            languages=languages,
            discovery={"te": self.telugu_discovery, "hi": self.hindi_discovery},
        )

    def _get_piper_voice(self, lang: str):
        if lang not in _PIPER_VOICES:
            raise RuntimeError("No Piper voice is configured for this language.")
        model, config, _ = self._voices[lang]
        key = f"{lang}:{model.resolve() if model else lang}"
        if key in _VOICE_CACHE:
            return _VOICE_CACHE[key]
        if not self._piper_ready(lang):
            label = _PIPER_VOICES[lang]["label"]
            setup = "SETUP_HINDI_TTS.bat" if lang == "hi" else "SETUP_TELUGU_TTS.bat"
            raise RuntimeError(f"{label} Piper voice is not ready. Run {setup} once.")
        from piper import PiperVoice
        voice = PiperVoice.load(str(model), config_path=str(config))
        _VOICE_CACHE[key] = voice
        return voice

    def _synthesize_piper(self, text: str, lang: str) -> Path:
        voice = self._get_piper_voice(lang)
        fd, name = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        out = Path(name)
        try:
            with wave.open(str(out), "wb") as wav_file:
                if hasattr(voice, "synthesize_wav"):
                    voice.synthesize_wav(text, wav_file)
                else:
                    voice.synthesize(text, wav_file)
            return out
        except Exception:
            out.unlink(missing_ok=True)
            raise

    @staticmethod
    def _clean_text_for_speech(text: str, lang: str) -> str:
        """Strip markdown and format symbols so offline TTS speaks cleanly without stuttering."""
        import re
        t = str(text or "")
        t = re.sub(r"\*\*([^*]+)\*\*", r"\1", t)
        t = re.sub(r"\*([^*]+)\*", r"\1", t)
        t = re.sub(r"__([^_]+)__", r"\1", t)
        t = re.sub(r"_([^_]+)_", r"\1", t)
        t = re.sub(r"^[\s*•\-#]+\s*", "", t, flags=re.MULTILINE)
        t = re.sub(r"[\s*•\-#]+", " ", t)
        conjunction = " या " if lang in {"hi", "hinglish", "mr"} else (" లేదా " if lang == "te" else (" அல்லது " if lang == "ta" else " or "))
        t = re.sub(r"\s*/\s*", conjunction, t)
        t = re.sub(r"[~^<>\"`@$%&]+", " ", t)
        return re.sub(r"\s+", " ", t).strip()

    def _synthesize_espeak(self, text: str, lang: str) -> Path:
        exe = self.espeak_executable
        voice = _ESPEAK_VOICES.get(lang)
        if not exe or not exe.is_file():
            raise RuntimeError("Multilingual offline TTS is not installed. Run SETUP_OFFLINE_TTS.bat once.")
        if not voice:
            raise RuntimeError(f"Offline TTS does not support language '{lang}'.")

        fd, name = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        out = Path(name)
        try:
            # -b 1 means UTF-8 input. Pass text via stdin to avoid Windows ANSI/CP1252 CLI argument corruption.
            # Speed: 135 wpm for Indic and 140 for English ensures natural, unhurried cadence without syllable clipping.
            # Word gap (-g 4): 40ms inter-word pause prevents phonetic collision and robotic stuttering.
            # Pitch (-p 50) and Amplitude (-a 100): Clear, balanced output without digital clipping.
            clean_text = self._clean_text_for_speech(text, lang)
            speed = "140" if lang == "en" else "135"
            cmd = [str(exe)]
            env = os.environ.copy()
            if self.espeak_data_parent:
                cmd.append(f"--path={self.espeak_data_parent}")
                env["ESPEAK_DATA_PATH"] = str(self.espeak_data_parent)
            cmd.extend(["-b", "1", "-v", voice, "-s", speed, "-p", "50", "-a", "100", "-w", str(out)])
            result = subprocess.run(
                cmd,
                input=clean_text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=25,
                check=False,
                env=env,
            )
            if result.returncode != 0 or not out.is_file() or out.stat().st_size <= 44:
                err_bytes = result.stderr if isinstance(result.stderr, bytes) else str(result.stderr or "").encode("utf-8", "replace")
                out_bytes = result.stdout if isinstance(result.stdout, bytes) else str(result.stdout or "").encode("utf-8", "replace")
                detail = (err_bytes.decode("utf-8", "replace") or out_bytes.decode("utf-8", "replace") or "eSpeak NG returned no audio").strip()
                raise RuntimeError(f"Offline speech generation failed: {detail[:240]}")
            return out
        except Exception:
            out.unlink(missing_ok=True)
            raise

    def synthesize(self, text: str, language: str) -> Path:
        lang = self._normalize_language(language)
        if lang not in _ESPEAK_VOICES:
            raise RuntimeError(f"Offline TTS does not support language '{language}'.")
        if not text.strip():
            raise ValueError("Text is empty.")

        # Prefer existing better-quality Piper voices for Hindi/Telugu.
        if lang in _PIPER_VOICES and self._piper_ready(lang):
            try:
                return self._synthesize_piper(text, lang)
            except Exception:
                # A corrupt Piper model should not kill offline speech if the
                # compact fallback is installed.
                if not self._espeak_ready():
                    raise

        return self._synthesize_espeak(text, lang)

    def play_on_device_async(self, text: str, language: str) -> None:
        """Start verified Windows playback and clean the temporary WAV later.

        V43 launched a background thread and returned HTTP 200 before winsound had
        even attempted playback.  A thread failure therefore looked like success in
        the UI and prevented the browser WAV fallback.  Here PlaySound(SND_ASYNC) is
        invoked on the request thread: if Windows rejects the WAV/device, the route
        fails immediately and the frontend can fall back.
        """
        if os.name != "nt":
            raise RuntimeError("Direct local speaker playback is available only on the Windows local runtime.")
        path = self.synthesize(text, language)
        try:
            import winsound
            # Validate the WAV and estimate how long it must remain on disk.
            with wave.open(str(path), "rb") as wf:
                frames = wf.getnframes()
                rate = max(1, wf.getframerate())
                duration = frames / rate
            winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        except Exception as exc:
            path.unlink(missing_ok=True)
            raise RuntimeError(f"Windows local speaker playback failed: {exc}") from exc

        def _cleanup_later():
            # SND_ASYNC may still be reading the file after PlaySound returns.
            # Keep it around for the full clip plus a small safety margin.
            import time
            time.sleep(max(1.0, duration + 1.0))
            path.unlink(missing_ok=True)

        threading.Thread(target=_cleanup_later, daemon=True, name="jeevikamitra-tts-cleanup").start()
