from pathlib import Path

from backend.models.beneficiary import BeneficiaryProfile
from backend.nlu.local_extractor import LocalProfileExtractor, normalize_contextual_transcript
from backend.stt_local import LocalSTT

ROOT = Path(__file__).resolve().parents[1]


def _patch(text: str, lang: str = "en"):
    return LocalProfileExtractor().extract_patch(text, BeneficiaryProfile(), lang)


def test_noisy_english_tenth_answers_are_canonicalised():
    for text in ["Tend the glass", "I have completed my teninth", "My headpo feature is tein"]:
        p = _patch(text, "en")
        assert p.education.level == "10th", text
        assert p.education.status == "passed", text
        assert normalize_contextual_transcript(text, "education", "en") == "10th class"


def test_noisy_hindi_tenth_answer_is_canonicalised():
    text = "टैेंथ क्लास"
    p = _patch(text, "hi")
    assert p.education.level == "10th"
    assert p.education.status == "passed"
    assert normalize_contextual_transcript(text, "education", "hi") == "10वीं कक्षा"


def test_telugu_tenth_remains_native_and_valid():
    text = "పదో తరగతి"
    p = _patch(text, "te")
    assert p.education.level == "10th"
    assert normalize_contextual_transcript(text, "education", "te") == "పదో తరగతి"


def test_observed_hindi_electrician_asr_variant_maps_to_electrical():
    p = _patch("मैं दो साल सेलट्रशन का काम करता हूं", "hi")
    assert "electrical" in p.skills


def test_context_normalizer_does_not_rewrite_general_speech():
    raw = "Tend the glass"
    assert normalize_contextual_transcript(raw, "location", "en") == raw


def test_offline_english_prefers_whisper_small_when_ready(monkeypatch, tmp_path):
    stt = LocalSTT()
    wav = tmp_path / "x.wav"
    wav.write_bytes(b"placeholder")
    monkeypatch.setattr(stt, "validate_wav", lambda _: (1, 2, 16000))
    monkeypatch.setattr(stt, "_faster_whisper_ready", lambda: True)
    monkeypatch.setattr(stt, "_transcribe_faster_whisper", lambda path, language: "I completed 10th class")
    monkeypatch.setattr(stt, "_sherpa_model_ready", lambda lang: True)
    text, engine = stt.transcribe(wav, "en")
    assert text == "I completed 10th class"
    assert engine == "faster-whisper-small-en"


def test_frontend_sends_expected_field_and_uses_direct_windows_tts_first():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "fd.append('expected_field'" in js
    direct = js.index("/tts/offline/play-local")
    wav = js.index("playAudioResponse('/tts/offline'", direct)
    assert direct < wav


def test_local_tts_playback_route_is_present():
    app = (ROOT / "backend" / "api" / "app.py").read_text(encoding="utf-8")
    assert '@app.post("/tts/offline/play-local"' in app
    assert "play_on_device_async" in app


def test_observed_telugu_two_year_phrase_keeps_duration():
    p = _patch("నేను రెండు సంవత్సరాల నుంచల్లి ఎలక్ట్రిషియన్ పనిచస్తున్నాను", "te")
    assert p.experience
    assert p.experience[0].duration_months == 24
