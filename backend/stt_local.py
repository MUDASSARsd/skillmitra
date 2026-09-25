"""Offline speech-to-text router.

Primary engine:
- Project-local faster-whisper multilingual model under <project>/models/.

Optional advanced fallbacks (only when explicitly configured): Parakeet,
AI4Bharat IndicConformer, and whisper.cpp. Normal V43 operation never requires
a previous project directory. All offline engines are local.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import wave
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]

# V43 primary Offline ASR for Indian languages: per-language IndicConformer
# CTC ONNX models exported for sherpa-onnx. These models are downloaded into
# this project only; no old JeevikaMitra folder or environment path is used.
_SHERPA_MODEL_ROOT = _ROOT / "models" / "indicconformer-sherpa-onnx"
_SHERPA_INDIC_UI_LANGS = ("hi", "te", "ta", "kn", "ml", "mr", "bn", "gu", "pa", "or")


INDIC_LANGUAGE_CODES = {
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai", "ml",
    "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur",
}

_MODEL_CACHE: dict[str, Any] = {}

_ASR_PROMPTS = {
    "en": "This is an Indian livelihood interview with Indian English accent. Words include education, tenth class, 10th pass, 12th pass, intermediate, diploma, ITI, electrician, house wiring, plumber, mechanic, two wheeler, bike repair, carpenter, welder, mason, tailoring, solar panel technician, AC repair, driver, housekeeping, data entry, work experience, years, months, fresher, job, self employment, business, shop, training, course, Hyderabad, Warangal, Vijayawada, Guntur, Delhi.",
    "hi": "यह भारतीय आजीविका और कौशल साक्षात्कार है। सामान्य शब्द: 10वीं पास, 12वीं पास, आईटीआई, डिप्लोमा, इलेक्ट्रिशियन, वायरिंग, प्लंबर, मैकेनिक, सिलाई, टेलर, राजमिस्त्री, मोबाइल रिपेयर, सोलर, एसी रिपेयर, ड्राइवर, अनुभव, साल, महीने, नौकरी, जॉब, स्वरोजगार, बिजनेस, दुकान, ट्रेनिंग, कोर्स, हैदराबाद।",
    "te": "ఇది జీవికా మిత్ర నైపుణ్య సంభాషణ. సాధారణ పదాలు: పదో తరగతి, 10th పాస్, ఇంటర్మీడియట్, ఐటీఐ, డిప్లొమా, ఎలక్ట్రీషియన్, వైరింగ్, ప్లంబర్, బైక్ మెకానిక్, టైలర్, మేస్త్రీ, మొబైల్ రిపేర్, సోలార్, డ్రైవర్, అనుభవం, సంవత్సరాలు, ఉద్యోగం, జాబ్, స్వయం ఉపాధి, బిజినెస్, షాప్, శిక్షణ, ట్రైనింగ్, హైదరాబాద్, వరంగల్, విజయవాడ, గుంటూరు.",
    "ta": "இது தமிழ் உரையாடல். கல்வி, 10ஆம் வகுப்பு, வேலை, அனுபவம், பயிற்சி, எலக்ட்ரீஷியன், பிளம்பர், மெக்கானிக் போன்ற சொற்கள் வரலாம்.",
    "kn": "ಇದು ಕನ್ನಡ ಸಂಭಾಷಣೆ. ಶಿಕ್ಷಣ, 10ನೇ ತರಗತಿ, ಕೆಲಸ, ಅನುಭವ, ಉದ್ಯೋಗ, ತರಬೇತಿ, ಎಲೆಕ್ಟ್ರಿಷಿಯನ್ ಪದಗಳು ಬರಬಹುದು.",
    "ml": "ഇത് മലയാള സംഭാഷണമാണ്. വിദ്യാഭ്യാസം, 10ാം ക്ലാസ്, ജോലി, പരിചയം, പരിശീലനം, ഇലക്ട്രീഷ്യൻ തുടങ്ങിയ വാക്കുകൾ വരാം.",
    "mr": "हे मराठी संभाषण आहे. शिक्षण, 10वी, काम, अनुभव, नोकरी, प्रशिक्षण, इलेक्ट्रीशियन असे शब्द येऊ शकतात.",
    "bn": "এটি বাংলা কথোপকথন। শিক্ষা, 10ম শ্রেণি, কাজ, অভিজ্ঞতা, চাকরি, প্রশিক্ষণ, ইলেকট্রিশিয়ান শব্দ আসতে পারে।",
    "gu": "આ ગુજરાતી વાતચીત છે. શિક્ષણ, 10મું ધોરણ, કામ, અનુભવ, નોકરી, તાલીમ, ઇલેક્ટ્રિશિયન જેવા શબ્દો આવી શકે છે.",
    "pa": "ਇਹ ਪੰਜਾਬੀ ਗੱਲਬਾਤ ਹੈ। ਪੜ੍ਹਾਈ, 10ਵੀਂ, ਕੰਮ, ਤਜਰਬਾ, ਨੌਕਰੀ, ਟ੍ਰੇਨਿੰਗ, ਇਲੈਕਟ੍ਰੀਸ਼ੀਅਨ ਵਰਗੇ ਸ਼ਬਦ ਆ ਸਕਦੇ ਹਨ।",
    "or": "ଏହା ଓଡ଼ିଆ କଥୋପକଥନ। ଶିକ୍ଷା, 10ମ ଶ୍ରେଣୀ, କାମ, ଅନୁଭବ, ଚାକିରି, ପ୍ରଶିକ୍ଷଣ, ଇଲେକ୍ଟ୍ରିସିଆନ ଭଳି ଶବ୍ଦ ଆସିପାରେ।",
}

_SCRIPT_RANGES = {
    "hi": ((0x0900, 0x097F),), "mr": ((0x0900, 0x097F),),
    "te": ((0x0C00, 0x0C7F),), "ta": ((0x0B80, 0x0BFF),),
    "kn": ((0x0C80, 0x0CFF),), "ml": ((0x0D00, 0x0D7F),),
    "bn": ((0x0980, 0x09FF),), "gu": ((0x0A80, 0x0AFF),),
    "pa": ((0x0A00, 0x0A7F),), "or": ((0x0B00, 0x0B7F),),
}


@dataclass
class LocalSTTStatus:
    ready: bool
    engine: str = "hybrid"
    detail: str | None = None
    english_ready: bool = False
    indic_ready: bool = False
    whisper_fallback_ready: bool = False
    faster_whisper_ready: bool = False
    parakeet_model_dir: str | None = None
    indic_model: str | None = None
    faster_whisper_model_dir: str | None = None
    sherpa_indic_ready: bool = False
    sherpa_ready_languages: list[str] | None = None
    language_engines: dict[str, str] | None = None

    def as_dict(self) -> dict:
        return asdict(self)


class LocalSTT:
    def __init__(self, binary_path: str | None = None, model_path: str | None = None):
        # V43 independence rule: normal operation never depends on paths from an
        # older project folder. The supported local microphone lives under
        # <project>/models/faster-whisper-*. Legacy external engines remain an
        # explicit advanced opt-in only.
        self.allow_external_paths = os.getenv("ALLOW_EXTERNAL_MODEL_PATHS", "0").strip().lower() in {"1", "true", "yes"}
        parakeet_env = os.getenv("PARAKEET_MODEL_DIR", "") if self.allow_external_paths else ""
        self.parakeet_dir = Path(parakeet_env) if parakeet_env else None
        self.indic_model = os.getenv("INDIC_ASR_MODEL", "ai4bharat/indic-conformer-600m-multilingual")
        wb = binary_path or (os.getenv("WHISPER_CPP_BIN", "") if self.allow_external_paths else "")
        wm = model_path or (os.getenv("WHISPER_MODEL_PATH", "") if self.allow_external_paths else "")
        self.whisper_bin = Path(wb) if wb else None
        self.whisper_model = Path(wm) if wm else None
        # Project-local multilingual fallback: no .env path is required.
        # Prefer the base model for Indic accuracy. Tiny is retained only as an
        # emergency fallback for older folders because it hallucinated too often
        # on natural Hindi/Telugu/Tamil speech in real jury tests.
        self.faster_whisper_tiny_dir = _ROOT / "models" / "faster-whisper-tiny"
        self.faster_whisper_base_dir = _ROOT / "models" / "faster-whisper-base"
        self.faster_whisper_small_dir = _ROOT / "models" / "faster-whisper-small"
        # Legacy Whisper fallback directories are retained only for backward compatibility.
        # Base/Tiny remain backward-compatible fallbacks when an older local model exists.
        if (self.faster_whisper_small_dir / "model.bin").is_file():
            self.faster_whisper_dir = self.faster_whisper_small_dir
        elif (self.faster_whisper_base_dir / "model.bin").is_file():
            self.faster_whisper_dir = self.faster_whisper_base_dir
        else:
            self.faster_whisper_dir = self.faster_whisper_tiny_dir
        self.sherpa_model_root = _SHERPA_MODEL_ROOT

    def _sherpa_model_ready(self, lang: str) -> bool:
        if importlib.util.find_spec("sherpa_onnx") is None:
            return False
        lang = (lang or "").lower()
        if lang == "en":
            return bool(
                (self.sherpa_model_root / "en" / "model.int8.onnx").is_file()
                and (self.sherpa_model_root / "en" / "tokens.txt").is_file()
            )
        if lang in _SHERPA_INDIC_UI_LANGS:
            return bool(
                (self.sherpa_model_root / lang / "model.int8.onnx").is_file()
                and (self.sherpa_model_root / "tokens.txt").is_file()
            )
        return False

    def _sherpa_hinglish_ready(self) -> bool:
        if importlib.util.find_spec("sherpa_onnx") is None:
            return False
        d = self.sherpa_model_root / "hi-hinglish-swift"
        return all((d / name).is_file() for name in ("encoder.int8.onnx", "decoder.int8.onnx", "tokens.txt"))

    def _sherpa_ready_languages(self) -> list[str]:
        return [lang for lang in ("en", *_SHERPA_INDIC_UI_LANGS) if self._sherpa_model_ready(lang)]

    def _english_ready(self) -> bool:
        if importlib.util.find_spec("sherpa_onnx") is None or not self.parakeet_dir:
            return False
        return all((self.parakeet_dir / name).is_file() for name in ("model.int8.onnx", "tokens.txt"))

    def _indic_ready(self) -> bool:
        # Dependencies alone do NOT mean the IndicConformer model is usable.
        # Only report it ready when the model files already exist locally.
        if importlib.util.find_spec("torch") is None or importlib.util.find_spec("transformers") is None:
            return False
        model_path = Path(self.indic_model)
        if model_path.is_dir() and (model_path / "config.json").is_file():
            return True
        try:
            from huggingface_hub import try_to_load_from_cache
            cached = try_to_load_from_cache(self.indic_model, "config.json")
            return isinstance(cached, str) and Path(cached).is_file()
        except Exception:
            return False

    def _whisper_ready(self) -> bool:
        return bool(self.whisper_bin and self.whisper_bin.is_file() and self.whisper_model and self.whisper_model.is_file())

    def _faster_whisper_ready(self) -> bool:
        return bool(
            importlib.util.find_spec("faster_whisper") is not None
            and self.faster_whisper_dir.is_dir()
            and (self.faster_whisper_dir / "model.bin").is_file()
        )

    def status(self) -> LocalSTTStatus:
        en_legacy = self._english_ready()
        indic_legacy = self._indic_ready()
        whisper_cpp = self._whisper_ready()
        faster_whisper = self._faster_whisper_ready()
        sherpa_langs = self._sherpa_ready_languages()
        sherpa_indic = any(lang in sherpa_langs for lang in _SHERPA_INDIC_UI_LANGS)
        whisper = whisper_cpp or faster_whisper
        ready = bool(sherpa_langs or en_legacy or indic_legacy or whisper)

        language_engines: dict[str, str] = {}
        for lang in ("en", *_SHERPA_INDIC_UI_LANGS):
            if lang == "en" and faster_whisper:
                language_engines[lang] = "Whisper Small (Indian-English primary)"
            elif lang in sherpa_langs:
                language_engines[lang] = "IndicConformer ONNX" if lang != "en" else "FastConformer ONNX fallback"
            elif faster_whisper:
                language_engines[lang] = "Whisper fallback"
            elif lang == "en" and en_legacy:
                language_engines[lang] = "Parakeet"
            elif lang in _SHERPA_INDIC_UI_LANGS and indic_legacy:
                language_engines[lang] = "AI4Bharat IndicConformer legacy"
            else:
                language_engines[lang] = "not installed"
        if self._sherpa_hinglish_ready():
            language_engines["hinglish"] = "Hinglish ONNX"
        else:
            language_engines["hinglish"] = "Whisper fallback" if faster_whisper else "not installed"

        parts = []
        if sherpa_langs:
            parts.append("Indic-first ONNX: " + ",".join(sherpa_langs))
        if self._sherpa_hinglish_ready():
            parts.append("Hinglish ONNX")
        if faster_whisper:
            parts.append("Whisper fallback")
        if en_legacy:
            parts.append("Parakeet fallback")
        if indic_legacy:
            parts.append("legacy IndicConformer")
        if whisper_cpp:
            parts.append("whisper.cpp fallback")
        detail = "Offline STT ready (" + "; ".join(parts) + ")." if ready else (
            "Offline microphone models are not installed. Run SETUP_INDEPENDENT_LOCAL.bat once. "
            "It installs the jury Hindi/Telugu/Tamil IndicConformer pack plus the local fallback inside this folder."
        )
        return LocalSTTStatus(
            ready=ready,
            detail=detail,
            english_ready=("en" in sherpa_langs) or en_legacy,
            indic_ready=sherpa_indic or indic_legacy,
            whisper_fallback_ready=whisper,
            faster_whisper_ready=faster_whisper,
            parakeet_model_dir=str(self.parakeet_dir) if self.parakeet_dir else None,
            indic_model=self.indic_model,
            faster_whisper_model_dir=str(self.faster_whisper_dir),
            sherpa_indic_ready=sherpa_indic,
            sherpa_ready_languages=sherpa_langs,
            language_engines=language_engines,
        )

    @staticmethod
    def validate_wav(path: Path) -> tuple[int, int, int]:
        try:
            with wave.open(str(path), "rb") as w:
                channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
                if channels != 1 or width != 2:
                    raise ValueError("Offline STT requires mono 16-bit PCM WAV audio.")
                if rate != 16000:
                    raise ValueError("Offline hybrid STT requires 16 kHz WAV audio.")
                return channels, width, rate
        except wave.Error as exc:
            raise ValueError("Invalid WAV audio.") from exc

    @staticmethod
    def _read_pcm16(path: Path):
        import numpy as np
        with wave.open(str(path), "rb") as w:
            samples = w.readframes(w.getnframes())
        return np.frombuffer(samples, dtype=np.int16).astype(np.float32) / 32768.0

    def _get_sherpa_recognizer(self, lang: str):
        lang = (lang or "").lower()
        key = f"sherpa-indic::{lang}"
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        if not self._sherpa_model_ready(lang):
            raise RuntimeError(f"Indic-first Offline ASR model for '{lang}' is not installed.")
        import sherpa_onnx
        if lang == "en":
            model = self.sherpa_model_root / "en" / "model.int8.onnx"
            tokens = self.sherpa_model_root / "en" / "tokens.txt"
        else:
            model = self.sherpa_model_root / lang / "model.int8.onnx"
            tokens = self.sherpa_model_root / "tokens.txt"
        recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
            model=str(model),
            tokens=str(tokens),
            num_threads=max(1, min(6, os.cpu_count() or 4)),
            decoding_method="greedy_search",
        )
        _MODEL_CACHE[key] = recognizer
        return recognizer

    def _transcribe_sherpa(self, path: Path, lang: str) -> str:
        recognizer = self._get_sherpa_recognizer(lang)
        samples = self._read_pcm16(path)
        if samples.size < 8000:
            raise ValueError("Recording was too short. Speak for at least half a second, then stop the microphone.")
        # Reject almost-silent PCM before ASR. This prevents CTC decoders from
        # inventing text from background noise.
        import numpy as np
        rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64)))
        if rms < 0.003:
            raise ValueError("Recording was too quiet. Speak closer to the microphone and try again.")
        peak = float(np.max(np.abs(samples)))
        if peak > 0 and peak < 0.20:
            samples = np.clip(samples * min(3.0, 0.55 / peak), -1.0, 1.0).astype(np.float32)
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, samples)
        recognizer.decode_stream(stream)
        text = (stream.result.text or "").strip()
        self._hallucination_guard(text, lang)
        self._script_guard(text, lang)
        return text

    def _get_sherpa_hinglish(self):
        key = "sherpa-hinglish-swift"
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        if not self._sherpa_hinglish_ready():
            raise RuntimeError("Hinglish Offline ASR pack is not installed.")
        import sherpa_onnx
        d = self.sherpa_model_root / "hi-hinglish-swift"
        recognizer = sherpa_onnx.OfflineRecognizer.from_whisper(
            encoder=str(d / "encoder.int8.onnx"),
            decoder=str(d / "decoder.int8.onnx"),
            tokens=str(d / "tokens.txt"),
            num_threads=max(1, min(6, os.cpu_count() or 4)),
            decoding_method="greedy_search",
            language="hi",
            task="transcribe",
        )
        _MODEL_CACHE[key] = recognizer
        return recognizer

    def _transcribe_sherpa_hinglish(self, path: Path) -> str:
        recognizer = self._get_sherpa_hinglish()
        samples = self._read_pcm16(path)
        if samples.size < 8000:
            raise ValueError("Recording was too short. Speak for at least half a second, then stop the microphone.")
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, samples)
        recognizer.decode_stream(stream)
        text = (stream.result.text or "").strip()
        self._hallucination_guard(text, "hinglish")
        return text

    def _get_parakeet(self):
        key = "parakeet"
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        if not self._english_ready():
            raise RuntimeError("Parakeet English ASR is not configured.")
        import sherpa_onnx
        recognizer = sherpa_onnx.OfflineRecognizer.from_nemo_ctc(
            model=str(self.parakeet_dir / "model.int8.onnx"),
            tokens=str(self.parakeet_dir / "tokens.txt"),
            num_threads=max(1, min(6, os.cpu_count() or 4)),
            sample_rate=16000,
            feature_dim=80,
        )
        _MODEL_CACHE[key] = recognizer
        return recognizer

    def _transcribe_english(self, path: Path) -> str:
        recognizer = self._get_parakeet()
        samples = self._read_pcm16(path)
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, samples)
        recognizer.decode_stream(stream)
        return (stream.result.text or "").strip()

    def _get_indic(self):
        key = f"indic::{self.indic_model}"
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        if not self._indic_ready():
            raise RuntimeError("AI4Bharat IndicConformer dependencies are not installed in this Python environment.")
        from transformers import AutoModel
        model = AutoModel.from_pretrained(
            self.indic_model,
            trust_remote_code=True,
            local_files_only=os.getenv("INDIC_LOCAL_ONLY", "1") != "0",
        )
        _MODEL_CACHE[key] = model
        return model

    def _transcribe_indic(self, path: Path, language: str) -> str:
        import torch
        samples = self._read_pcm16(path)
        if samples.size < 3200:
            raise ValueError("Recording was too short or empty. Speak for at least 1 second, then stop the microphone.")
        wav = torch.from_numpy(samples).float().unsqueeze(0)
        model = self._get_indic()
        result = model(wav, language, "ctc")
        if isinstance(result, (tuple, list)):
            result = result[0]
        return str(result).strip()

    def _get_faster_whisper(self):
        key = f"faster-whisper::{self.faster_whisper_dir}"
        if key in _MODEL_CACHE:
            return _MODEL_CACHE[key]
        if not self._faster_whisper_ready():
            raise RuntimeError("Project-local faster-whisper model is not configured. Run SETUP_OFFLINE_STT.bat once.")
        from faster_whisper import WhisperModel
        model = WhisperModel(
            str(self.faster_whisper_dir),
            device="cpu",
            compute_type="int8",
            cpu_threads=max(1, min(8, os.cpu_count() or 4)),
            num_workers=1,
        )
        _MODEL_CACHE[key] = model
        return model


    @staticmethod
    def _hallucination_guard(text: str, lang: str) -> None:
        """Reject Whisper repetition loops instead of auto-sending them to the chat.

        Real failure examples seen on jury hardware included hundreds of repeated
        Devanagari characters and Telugu tokens such as "పను, పను, పను...".
        Those outputs are worse than asking the user to repeat once.
        """
        import re
        raw = (text or "").strip()
        if not raw:
            raise RuntimeError("No clear speech was detected. Please speak again.")

        # A single alphabetic character repeated many times is a classic decoder loop.
        if re.search(r"([A-Za-z\u0900-\u0D7F])\1{7,}", raw):
            raise RuntimeError("Local speech recognition detected a repetition loop. Please speak again clearly.")

        tokens = [t for t in re.findall(r"[\w\u0900-\u0D7F]+", raw.lower(), flags=re.UNICODE) if t]
        if len(tokens) >= 7:
            from collections import Counter
            counts = Counter(tokens)
            top_count = counts.most_common(1)[0][1]
            unique_ratio = len(counts) / len(tokens)
            # Reject dominant repeated words or very low lexical diversity.
            if top_count >= 5 and top_count / len(tokens) >= 0.45:
                raise RuntimeError("Local speech recognition detected repeated words. Please speak again clearly.")
            if len(tokens) >= 10 and unique_ratio <= 0.22:
                raise RuntimeError("Local speech recognition was not reliable enough. Please speak again clearly.")

        # Catch consecutive short-token loops even when punctuation changes.
        run = 1
        for a, b in zip(tokens, tokens[1:]):
            if a == b and len(a) <= 12:
                run += 1
                if run >= 4:
                    raise RuntimeError("Local speech recognition detected a repetition loop. Please speak again clearly.")
            else:
                run = 1

    @staticmethod
    def _script_guard(text: str, lang: str) -> None:
        """Reject obvious foreign-script hallucinations (e.g. Cyrillic, CJK, Arabic) from mic noise."""
        if not text or lang in {"en", "hinglish"}:
            return
        letters = [c for c in text if c.isalpha()]
        if len(letters) < 4:
            return
        if lang in _SCRIPT_RANGES:
            ranges = _SCRIPT_RANGES[lang]
            native_count = sum(any(lo <= ord(c) <= hi for lo, hi in ranges) for c in letters)
            if native_count == 0 and len(text.split()) >= 3:
                raise RuntimeError(
                    f"{lang} transcription was not reliable enough. Please speak again clearly; "
                    "the local ASR rejected an unexpected script result."
                )

    def _transcribe_faster_whisper(self, path: Path, language: str) -> str:
        model = self._get_faster_whisper()
        requested = language or "en"
        lang = {"hinglish": "hi"}.get(requested, requested)
        is_indic = lang in INDIC_LANGUAGE_CODES
        segments, _ = model.transcribe(
            str(path),
            language=lang,
            task="transcribe",
            initial_prompt=_ASR_PROMPTS.get(lang),
            beam_size=5 if is_indic else 3,
            best_of=5 if is_indic else 3,
            patience=1.0,
            repetition_penalty=1.18 if is_indic else 1.10,
            no_repeat_ngram_size=3,
            vad_filter=True,
            vad_parameters={
                "threshold": 0.50,
                "min_speech_duration_ms": 200,
                "min_silence_duration_ms": 400,
                "speech_pad_ms": 200,
            },
            condition_on_previous_text=False,
            word_timestamps=False,
            temperature=0.0,
            max_new_tokens=96,
        )
        text = " ".join(segment.text.strip() for segment in segments if segment.text.strip()).strip()
        self._hallucination_guard(text, requested)
        self._script_guard(text, requested)
        return text

    def _transcribe_whisper(self, path: Path, language: str) -> str:
        if not self._whisper_ready():
            raise RuntimeError("whisper.cpp fallback is not configured.")
        lang = {"hinglish": "hi"}.get(language, language or "auto")
        cmd = [str(self.whisper_bin), "-m", str(self.whisper_model), "-f", str(path), "-l", lang, "-otxt", "-nt", "-np"]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False)
        out_file = Path(str(path) + ".txt")
        text = out_file.read_text(encoding="utf-8").strip() if out_file.exists() else proc.stdout.strip()
        if proc.returncode != 0 and not text:
            raise RuntimeError((proc.stderr or "whisper.cpp transcription failed").strip())
        return text

    def warmup(self) -> bool:
        """Load the project-local multilingual model once at app startup.

        This moves the several-second first-load cost away from the first jury mic turn.
        """
        if not self._faster_whisper_ready():
            return False
        try:
            self._get_faster_whisper()
            return True
        except Exception:
            return False

    def transcribe(self, wav_path: Path, language: str = "en") -> tuple[str, str]:
        self.validate_wav(wav_path)
        selected_lang = (language or "en").lower().split("-")[0]
        lang = "hi" if selected_lang == "hinglish" else selected_lang

        errors: list[str] = []

        # V43: Indian-accented English tested better with Whisper Small than the
        # generic English FastConformer pack on the jury laptop.  Keep the
        # IndicConformer-first path for Indian-script languages.
        if lang == "en" and self._faster_whisper_ready():
            try:
                return self._transcribe_faster_whisper(wav_path, "en"), "faster-whisper-small-en"
            except Exception as exc:
                errors.append(f"English Whisper Small: {str(exc).splitlines()[0][:240]}")

        # Indian-script languages use IndicConformer ONNX first. Whisper remains
        # a fallback because it previously hallucinated on natural Indic speech.
        if selected_lang != "hinglish" and self._sherpa_model_ready(lang):
            try:
                return self._transcribe_sherpa(wav_path, lang), (
                    "sherpa-fastconformer" if lang == "en" else "sherpa-indicconformer"
                )
            except Exception as exc:
                errors.append(f"Indic-first ASR: {str(exc).splitlines()[0][:240]}")

        if selected_lang == "hinglish":
            if self._sherpa_hinglish_ready():
                try:
                    return self._transcribe_sherpa_hinglish(wav_path), "sherpa-hinglish-swift"
                except Exception as exc:
                    errors.append(f"Hinglish ONNX: {str(exc).splitlines()[0][:240]}")
            if self._faster_whisper_ready():
                try:
                    return self._transcribe_faster_whisper(wav_path, selected_lang), "faster-whisper-hinglish-fallback"
                except Exception as exc:
                    errors.append(f"Hinglish Whisper fallback: {str(exc).splitlines()[0][:240]}")
            else:
                errors.append("Hinglish local model is not installed.")
        elif lang == "en":
            # English can use the small multilingual fallback when the optional
            # FastConformer pack is not installed.
            if self._faster_whisper_ready():
                try:
                    return self._transcribe_faster_whisper(wav_path, "en"), "faster-whisper"
                except Exception as exc:
                    errors.append(f"Whisper fallback: {str(exc).splitlines()[0][:240]}")
            if self._english_ready():
                try:
                    return self._transcribe_english(wav_path), "sherpa-parakeet"
                except Exception as exc:
                    errors.append(f"Parakeet: {exc}")
        elif lang in INDIC_LANGUAGE_CODES:
            # Keep Whisper only as a compatibility fallback for languages whose
            # IndicConformer pack has not been downloaded yet.
            if self._faster_whisper_ready():
                try:
                    return self._transcribe_faster_whisper(wav_path, selected_lang), "faster-whisper-fallback"
                except Exception as exc:
                    errors.append(f"Whisper fallback: {str(exc).splitlines()[0][:240]}")
            if self._indic_ready():
                try:
                    text = self._transcribe_indic(wav_path, lang)
                    self._hallucination_guard(text, selected_lang)
                    self._script_guard(text, selected_lang)
                    return text, "ai4bharat-indicconformer-legacy"
                except Exception as exc:
                    errors.append(f"Legacy IndicConformer: {str(exc).splitlines()[0][:240]}")
            if not self._sherpa_model_ready(lang):
                errors.append(
                    f"High-accuracy Offline {lang} pack is not installed. "
                    "Run SETUP_ALL_OFFLINE_LANGUAGES.bat or SETUP_INDEPENDENT_LOCAL.bat for jury languages."
                )
        else:
            errors.append(f"Unsupported selected language code: {lang}")

        if self._whisper_ready():
            try:
                return self._transcribe_whisper(wav_path, lang), "whisper.cpp-fallback"
            except Exception as exc:
                errors.append(f"whisper.cpp fallback: {exc}")

        raise RuntimeError("; ".join(errors) or "No offline ASR engine available.")

