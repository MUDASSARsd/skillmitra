from pathlib import Path

import pytest

from backend.stt_local import LocalSTT
from backend.tts_local import LocalTTS

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("text,lang", [
    ("चुववववववववववववववववववव", "hi"),
    ("प्रशा, प्रशा, प्रशा, प्रशा, प्रशा, प्रशा, प्रशा, प्रशा", "hi"),
    ("పను, పను, పను, పను, పను, పను, పను, పను", "te"),
])
def test_repetition_hallucinations_are_rejected(text, lang):
    with pytest.raises(RuntimeError):
        LocalSTT._hallucination_guard(text, lang)


def test_normal_native_sentences_are_not_rejected():
    LocalSTT._hallucination_guard("मैं दसवीं तक पढ़ा हूँ और दो साल से इलेक्ट्रिशियन का काम करता हूँ", "hi")
    LocalSTT._hallucination_guard("నేను పదో తరగతి చదివాను మరియు రెండు సంవత్సరాలుగా ఎలక్ట్రీషియన్ పని చేస్తున్నాను", "te")


def test_v41_prefers_small_model_and_strict_decoder():
    code = (ROOT / "backend" / "stt_local.py").read_text(encoding="utf-8")
    setup = (ROOT / "setup_offline_stt.py").read_text(encoding="utf-8")
    assert "faster-whisper-small" in code
    assert "Systran/faster-whisper-small" in setup
    assert "repetition_penalty=1.18" in code
    assert "no_repeat_ngram_size=3" in code
    assert "max_new_tokens=96" in code


def test_frontend_unlocks_web_audio_and_stops_assistant_before_recording():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "async function unlockAudioOutput()" in js
    assert "ttsAudioContext.decodeAudioData" in js
    assert "window.speechSynthesis?.cancel()" in js
    assert "activeAudioSource" in js


def test_tts_discovers_project_local_recursive_espeak(monkeypatch, tmp_path):
    root = tmp_path / "tools" / "espeak-ng" / "package" / "Program Files" / "eSpeak NG"
    root.mkdir(parents=True)
    exe = root / "espeak-ng.exe"
    exe.write_bytes(b"fake")
    import backend.tts_local as mod
    monkeypatch.setattr(mod, "_ROOT", tmp_path)
    monkeypatch.setattr(mod.shutil, "which", lambda _: None)
    assert LocalTTS._discover_espeak_ng() == exe


def test_setup_tts_has_project_local_official_msi_and_validation():
    bat = (ROOT / "SETUP_OFFLINE_TTS.bat").read_text(encoding="utf-8")
    assert "espeak-ng.msi" in bat
    assert "msiexec /a" in bat
    assert "Offline multilingual TTS validation passed" in bat
