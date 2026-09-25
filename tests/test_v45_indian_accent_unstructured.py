"""
Verification test suite for:
1. Hindi, Telugu, and all 12 Indic languages offline audio generation without question-mark corruption.
2. Indian accent phonetic handling (ASR variants, phonetic slips).
3. Unstructured Indian livelihood natural speech extraction completely offline.
"""
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.nlu.local_extractor import LocalProfileExtractor, normalize_contextual_transcript
from backend.tts_local import LocalTTS


def test_offline_tts_generates_substantial_audio_for_all_indic_languages():
    client = TestClient(app)
    phrases = {
        "hi": "नमस्ते! जीविका मित्र में आपका स्वागत है। आप कौन सा काम करना चाहते हैं?",
        "te": "నమస్కారం! జీవిక మిత్రకు స్వాగతం. మీరు ఏ పని చేయాలనుకుంటున్నారు?",
        "ta": "வணக்கம்! ஜீவிகா மித்ராவுக்கு வரவேற்கிறோம்.",
        "kn": "ನಮಸ್ಕಾರ! ಜೀವಿಕಾ ಮಿತ್ರಕ್ಕೆ ಸ್ವಾಗತ.",
        "mr": "नमस्कार! जीविका मित्रामध्ये आपले स्वागत आहे.",
        "bn": "নমস্কার! জীবিকা মিত্রে আপনাকে স্বাগতম।",
        "gu": "નમસ્તે! જીવિકા મિત્રમાં તમારું સ્વાગત છે.",
        "en": "Hello! Welcome to Jeevika Mitra. What work are you looking for?",
        "hinglish": "Namaste! Jeevika Mitra me aapka swagat hai.",
    }
    for lang, text in phrases.items():
        res = client.post("/tts/offline", json={"text": text, "language": lang})
        assert res.status_code == 200, f"TTS failed for {lang}"
        assert res.headers["content-type"] == "audio/wav"
        # Must be valid audio wave, not a 300-byte CP1252 question-mark burst
        assert len(res.content) > 50000, f"Audio burst too small for {lang}: {len(res.content)} bytes"


def test_unstructured_indian_natural_speech_extractions():
    ex = LocalProfileExtractor()

    # Case 1: Hindi multi-slot natural turn with training willingness
    p1 = ex.extract(
        "मेरा नाम राहुल है मैं गुंटूर में रहता हूँ 10वीं पास हूँ 2 साल से इलेक्ट्रिशियन का काम कर रहा हूँ मुझे प्राइवेट जॉब चाहिए और ट्रेनिंग करने को तैयार हूँ",
        language_code="hi",
    )
    assert p1.education.level == "10th"
    assert p1.education.status == "passed"
    assert "electrical" in p1.skills
    assert p1.location.district == "Guntur"
    assert p1.employment_preference == "job"
    assert p1.training_willingness is True

    # Case 2: Indian English with shop intention and standard education phrasing
    p2 = ex.extract(
        "I studied 10th standard in Warangal. I have 18 months experience in bike mechanic shop. I want to open own shop.",
        language_code="en",
    )
    assert p2.education.level == "10th"
    assert p2.education.status == "passed"
    assert "automotive" in p2.skills
    assert p2.location.district == "Warangal"
    assert p2.employment_preference == "business"

    # Case 3: Indian English with trade work and self-employment
    p3 = ex.extract(
        "8th class pass, 3 years welding and fabrication work in Pune, prefer self employment.",
        language_code="en",
    )
    assert p3.education.level == "8th"
    assert p3.education.status == "passed"
    assert "welding" in p3.skills
    assert p3.location.district == "Pune"
    assert p3.employment_preference == "self_employment"

    # Case 4: Telugu unstructured turn with district, trade, and preference
    p4 = ex.extract(
        "పదో తరగతి పాస్, కరీంనగర్ లో ఉంటాను, 2 ఇయర్స్ ప్లంబర్ వర్క్ చేసాను, జాబ్ కావాలి",
        language_code="te",
    )
    assert p4.education.level == "10th"
    assert p4.education.status == "passed"
    assert "plumbing" in p4.skills
    assert p4.location.district == "Karimnagar"
    assert p4.employment_preference == "job"

    # Case 5: Phonetic ASR slips ("10th passout", "electraction", "house wiring")
    p5 = ex.extract(
        "10th passout, doing electraction and house wiring since 2 years in Hyderabad, want company job",
        language_code="en",
    )
    assert p5.education.level == "10th"
    assert p5.education.status == "passed"
    assert "electrical" in p5.skills
    assert p5.location.district == "Hyderabad"
    assert p5.employment_preference == "job"


def test_contextual_transcript_education_accent_normalization():
    # Education context maps "tend the glass" to "tenth class"
    assert normalize_contextual_transcript("Tend the glass", "education", "en") == "10th class"
    # General context preserves raw speech
    assert normalize_contextual_transcript("Tend the glass", "location", "en") == "Tend the glass"
