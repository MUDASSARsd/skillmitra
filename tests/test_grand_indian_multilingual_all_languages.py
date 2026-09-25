"""
GRAND INDIAN MULTILINGUAL MATRIX TEST SUITE
Covers all 12 project languages with authentic Indian accent, colloquial idioms,
vernacular phonetics, unstructured speech extraction, offline conversation flow,
and local audio (TTS) synthesis with zero question-mark corruption.

Languages:
1. Hindi (hi)
2. Telugu (te)
3. Tamil (ta)
4. Kannada (kn)
5. Malayalam (ml)
6. Marathi (mr)
7. Bengali (bn)
8. Gujarati (gu)
9. Punjabi (pa)
10. Odia (or)
11. Indian English (en)
12. Hinglish (hinglish)
"""
import pytest
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.nlu.local_extractor import LocalProfileExtractor
from backend.tts_local import LocalTTS

ALL_12_INDIAN_TEST_CASES = [
    {
        "lang": "hi",
        "name": "Hindi",
        "text": "मेरा नाम अमित है, मैं लखनऊ में रहता हूँ, 10वीं पास हूँ, 2 साल से इलेक्ट्रिशियन का काम कर रहा हूँ, मुझे प्राइवेट जॉब चाहिए और ट्रेनिंग करने को तैयार हूँ",
        "expected_level": "10th",
        "expected_skill": "electrical",
        "expected_district": "Lucknow",
        "expected_pref": "job",
        "expected_months": 24,
    },
    {
        "lang": "te",
        "name": "Telugu",
        "text": "నా పేరు రవి, నేను వరంగల్ లో ఉంటాను, 10వ తరగతి పాస్, 1 సంవత్సరం బైక్ మెకానిక్ పని చేశాను, సొంత బిజినెస్ పెట్టాలి",
        "expected_level": "10th",
        "expected_skill": "automotive",
        "expected_district": "Warangal",
        "expected_pref": "business",
        "expected_months": 12,
    },
    {
        "lang": "ta",
        "name": "Tamil",
        "text": "நான் கோயம்புத்தூர் வசிக்கிறேன், 10ஆம் வகுப்பு பாஸ், 2 வருடங்கள் தையல் வேலை செய்தேன், சொந்த தொழில் செய்ய வேண்டும்",
        "expected_level": "10th",
        "expected_skill": "tailoring",
        "expected_district": "Coimbatore",
        "expected_pref": "self_employment",
        "expected_months": 24,
    },
    {
        "lang": "kn",
        "name": "Kannada",
        "text": "ನಾನು ಬೆಂಗಳೂರು ನಿವಾಸಿ, 10ನೇ ತರಗತಿ ಪಾಸ್, 1 ವರ್ಷ ಪ್ಲಂಬಿಂಗ್ ಕೆಲಸ ಮಾಡಿದ್ದೇನೆ, ಉದ್ಯೋಗ ಬೇಕು",
        "expected_level": "10th",
        "expected_skill": "plumbing",
        "expected_district": "Bengaluru",
        "expected_pref": "job",
        "expected_months": 12,
    },
    {
        "lang": "ml",
        "name": "Malayalam",
        "text": "ഞാൻ കൊച്ചി സ്വദേശി, 10ാം ക്ലാസ് പാസായി, 2 വർഷം വെൽഡിംഗ് ജോലി ചെയ്തു, ജോലി വേണം",
        "expected_level": "10th",
        "expected_skill": "welding",
        "expected_district": "Ernakulam",
        "expected_pref": "job",
        "expected_months": 24,
    },
    {
        "lang": "mr",
        "name": "Marathi",
        "text": "मी पुण्यात राहतो, 10वी पास आहे, 2 वर्षे बांधकाम गवंडी काम केले आहे, स्वतःचा व्यवसाय करायचा आहे",
        "expected_level": "10th",
        "expected_skill": "masonry",
        "expected_district": "Pune",
        "expected_pref": "business",
        "expected_months": 24,
    },
    {
        "lang": "bn",
        "name": "Bengali",
        "text": "আমি কলকাতায় থাকি, 10ম শ্রেণি পাশ, 1 বছর ডেইরি দুধের কাজ করেছি, চাকরি চাই",
        "expected_level": "10th",
        "expected_skill": "dairy",
        "expected_district": "Kolkata",
        "expected_pref": "job",
        "expected_months": 12,
    },
    {
        "lang": "gu",
        "name": "Gujarati",
        "text": "હું અમદાવાદમાં રહું છું, 10મું ધોરણ પાસ, 2 વર્ષ સોલાર પેનલનું કામ કર્યું છે, નોકરી જોઈએ",
        "expected_level": "10th",
        "expected_skill": "solar",
        "expected_district": "Ahmedabad",
        "expected_pref": "job",
        "expected_months": 24,
    },
    {
        "lang": "pa",
        "name": "Punjabi",
        "text": "ਮੈਂ ਲੁਧਿਆਣਾ ਵਿੱਚ ਰਹਿੰਦਾ ਹਾਂ, 10ਵੀਂ ਕਲਾਸ ਪਾਸ, 2 ਸਾਲ ਤੋਂ ਬਿਜਲੀ ਦਾ ਕੰਮ ਕਰ ਰਿਹਾ ਹਾਂ, ਨੌਕਰੀ ਚਾਹੀਦੀ ਹੈ",
        "expected_level": "10th",
        "expected_skill": "electrical",
        "expected_district": "Ludhiana",
        "expected_pref": "job",
        "expected_months": 24,
    },
    {
        "lang": "or",
        "name": "Odia",
        "text": "ମୁଁ ଭୁବନେଶ୍ୱର ରେ ରହୁଛି, 10ମ ଶ୍ରେଣୀ ପାସ୍, 1 ବର୍ଷ ମୋବାଇଲ୍ ରିପେୟାର କାମ କରିଛି, ଚାକିରି ଚାହୁଁଛି",
        "expected_level": "10th",
        "expected_skill": "mobile repair",
        "expected_district": "Khordha",
        "expected_pref": "job",
        "expected_months": 12,
    },
    {
        "lang": "en",
        "name": "Indian English",
        "text": "I completed 10th standard in Hyderabad. Doing electraction house wiring since 2 years. Want company job and willing for training.",
        "expected_level": "10th",
        "expected_skill": "electrical",
        "expected_district": "Hyderabad",
        "expected_pref": "job",
        "expected_months": 24,
    },
    {
        "lang": "hinglish",
        "name": "Hinglish",
        "text": "Mera naam suresh hai, main Indore me rehta hu, 12th pass hu, 2 saal se motor mechanic shop me bike repair ka kaam kiya hu, apna business start karna chahta hu.",
        "expected_level": "12th",
        "expected_skill": "automotive",
        "expected_district": "Indore",
        "expected_pref": "business",
        "expected_months": 24,
    },
]


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.mark.parametrize("case", ALL_12_INDIAN_TEST_CASES, ids=[c["name"] for c in ALL_12_INDIAN_TEST_CASES])
def test_all_12_languages_unstructured_extraction(case):
    """Test deterministic offline extraction of Indian accent unstructured speech for all 12 languages."""
    extractor = LocalProfileExtractor()
    profile = extractor.extract(case["text"], language_code=case["lang"])

    assert profile.education.level == case["expected_level"], (
        f"[{case['name']}] Education level mismatch: expected {case['expected_level']}, got {profile.education.level}"
    )
    assert profile.education.status == "passed", (
        f"[{case['name']}] Education status mismatch: expected 'passed', got {profile.education.status}"
    )
    assert case["expected_skill"] in profile.skills, (
        f"[{case['name']}] Skill mismatch: expected '{case['expected_skill']}' in {profile.skills}"
    )
    assert profile.location.district == case["expected_district"], (
        f"[{case['name']}] District mismatch: expected '{case['expected_district']}', got '{profile.location.district}'"
    )
    assert profile.employment_preference == case["expected_pref"], (
        f"[{case['name']}] Preference mismatch: expected '{case['expected_pref']}', got '{profile.employment_preference}'"
    )
    if case["expected_months"]:
        assert profile.experience, f"[{case['name']}] Expected experience duration to be extracted"
        assert profile.experience[0].duration_months == case["expected_months"], (
            f"[{case['name']}] Duration mismatch: expected {case['expected_months']}, got {profile.experience[0].duration_months}"
        )


@pytest.mark.parametrize("case", ALL_12_INDIAN_TEST_CASES, ids=[c["name"] for c in ALL_12_INDIAN_TEST_CASES])
def test_all_12_languages_offline_conversation_api(client, case):
    """Test full /conversation/offline pipeline for all 12 languages."""
    res = client.post(
        "/conversation/offline",
        json={
            "text": case["text"],
            "language_code": case["lang"],
            "include_recommendations": True,
        },
    )
    assert res.status_code == 200, f"[{case['name']}] API call failed: {res.text}"
    data = res.json()
    assert data["extraction_mode"].startswith("offline_"), f"[{case['name']}] Invalid extraction mode: {data['extraction_mode']}"
    assert data["profile"]["education"]["level"] == case["expected_level"]
    assert (data.get("next_question") is not None) or data.get("ready_for_mapping"), f"[{case['name']}] Missing assistant response"


@pytest.mark.parametrize("case", ALL_12_INDIAN_TEST_CASES, ids=[c["name"] for c in ALL_12_INDIAN_TEST_CASES])
def test_all_12_languages_offline_tts_audio_quality(client, case):
    """Test offline TTS synthesis for all 12 Indian languages producing full audio without CP1252 corruption."""
    res = client.post(
        "/tts/offline",
        json={
            "text": case["text"][:120],  # first sentence
            "language": case["lang"],
        },
    )
    assert res.status_code == 200, f"[{case['name']}] TTS synthesis failed: {res.text}"
    assert res.headers["content-type"] == "audio/wav"
    audio_bytes = len(res.content)
    # A corrupted CP1252 '????' clip produces < 5,000 bytes. A real 3-6 second utterance produces > 50,000 bytes.
    assert audio_bytes > 50000, f"[{case['name']}] Audio too small ({audio_bytes} bytes), likely corrupted."
