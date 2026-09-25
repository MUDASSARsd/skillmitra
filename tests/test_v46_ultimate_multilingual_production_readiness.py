"""
V46 Ultimate Multilingual Production Readiness Test Suite
Tests:
1. 12 Brand New Unstructured Real-World Indian Dialect Scenarios across all 12 languages.
2. Complete Audio WAV Structural & Acoustical Integrity (WAV PCM headers, duration > 1.5s, non-silence RMS).
3. 3-Turn Multi-Turn Offline Conversation Persistence & State Accumulation.
4. Deterministic NQR Qualification Retrieval & Scheme Matching from SQLite database.
5. Indian Accent Phonetic Robustness & Adversarial Edge Cases.
"""
import io
import math
import struct
import wave
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.models.beneficiary import BeneficiaryProfile
from backend.nlu.local_extractor import LocalProfileExtractor, normalize_contextual_transcript
from backend.tts_local import LocalTTS

NEW_12_INDIAN_SCENARIOS = [
    {
        "lang": "hi",
        "name": "Hindi (Kanpur Welder)",
        "text": "नमस्ते सर, मैं 8वीं पास हूँ, 3 साल से वेल्डिंग और ग्राइंडिंग का काम कर रहा हूँ, कानपुर में रहता हूँ, खुद का काम शुरू करना चाहता हूँ।",
        "expected_level": "8th",
        "expected_skill": "welding",
        "expected_district": "Kanpur",
        "expected_pref": "self_employment",
        "expected_months": 36,
    },
    {
        "lang": "te",
        "name": "Telugu (Nizamabad AC Repair)",
        "text": "అయ్యా, నేను 10వ తరగతి పాస్ అయ్యాను, నిజామాబాద్ లో ఉంటాను, 2 ఇయర్స్ ఎయిర్ కండిషనర్ మరియు ఫ్రిజ్ రిపేర్ పని చేశాను, కంపెనీ జాబ్ కావాలి, ట్రైనింగ్ తీసుకుంటాను.",
        "expected_level": "10th",
        "expected_skill": "refrigeration and ac",
        "expected_district": "Nizamabad",
        "expected_pref": "job",
        "expected_months": 24,
        "expected_training": True,
    },
    {
        "lang": "ta",
        "name": "Tamil (Madurai Data Entry)",
        "text": "வணக்கம், நான் 12ஆம் வகுப்பு முடித்தேன், மதுரையில் வசிக்கிறேன், 1 வருடம் கணினி டேட்டா என்ட்ரி வேலை செய்தேன், அலுவலக வேலை வேண்டும்.",
        "expected_level": "12th",
        "expected_skill": "data entry",
        "expected_district": "Madurai",
        "expected_pref": "job",
        "expected_months": 12,
    },
    {
        "lang": "kn",
        "name": "Kannada (Mysore Beauty Parlour)",
        "text": "ನಮಸ್ಕಾರ, ನಾನು ಮೈಸೂರು ನಿವಾಸಿ, 10ನೇ ತರಗತಿ ಪಾಸ್, 2 ವರ್ಷ ಬ್ಯೂಟಿ ಪಾರ್ಲರ್ ಕೆಲಸ ಮಾಡಿದ್ದೇನೆ, ಸ್ವಂತ ಅಂಗಡಿ ತೆರೆಯಬೇಕು.",
        "expected_level": "10th",
        "expected_skill": "beauty",
        "expected_district": "Mysuru",
        "expected_pref": "business",
        "expected_months": 24,
    },
    {
        "lang": "ml",
        "name": "Malayalam (Kozhikode Carpenter)",
        "text": "ഹലോ, ഞാൻ കോഴിക്കോട് സ്വദേശി, 10ാം ക്ലാസ് പാസായി, 1.5 വർഷം കാർപെന്റർ ഫർണിച്ചർ ജോലി ചെയ്തു, ജോലി വേണം.",
        "expected_level": "10th",
        "expected_skill": "carpentry",
        "expected_district": "Kozhikode",
        "expected_pref": "job",
        "expected_months": 18,
    },
    {
        "lang": "mr",
        "name": "Marathi (Nashik Security Guard)",
        "text": "नमस्कार, मी नाशिक मध्ये राहतो, 12वी पास आहे, 2 वर्षे सिक्युरिटी गार्ड काम केले आहे, खाजगी नोकरी पाहिजे.",
        "expected_level": "12th",
        "expected_skill": "security",
        "expected_district": "Nashik",
        "expected_pref": "job",
        "expected_months": 24,
    },
    {
        "lang": "bn",
        "name": "Bengali (Howrah Bakery)",
        "text": "নমস্কার, আমি হাওড়ায় থাকি, 10ম শ্রেণি পাশ, 2 বছর বেকারি কেক ও বিস্কুট তৈরির কাজ করেছি, নিজস্ব দোকান খুলতে চাই।",
        "expected_level": "10th",
        "expected_skill": "baking",
        "expected_district": "Howrah",
        "expected_pref": "business",
        "expected_months": 24,
    },
    {
        "lang": "gu",
        "name": "Gujarati (Vadodara Warehouse)",
        "text": "નમસ્તે, હું વડોદરામાં રહું છું, 10મું ધોરણ પાસ, 1 વર્ષ વેરહાઉસ પેકિંગ કામ કર્યું છે, કંપનીમાં નોકરી જોઈએ.",
        "expected_level": "10th",
        "expected_skill": "warehouse",
        "expected_district": "Vadodara",
        "expected_pref": "job",
        "expected_months": 12,
    },
    {
        "lang": "pa",
        "name": "Punjabi (Amritsar Carpenter)",
        "text": "ਸਤਿ ਸ੍ਰੀ ਅਕਾਲ, ਮੈਂ ਅੰਮ੍ਰਿਤਸਰ ਵਿੱਚ ਰਹਿੰਦਾ ਹਾਂ, 10ਵੀਂ ਕਲਾਸ ਪਾਸ, 2 ਸਾਲ ਤੋਂ ਕਾਰਪੇਂਟਰ ਲੱਕੜ ਦਾ ਕੰਮ ਕੀਤਾ ਹੈ, ਨੌਕਰੀ ਚਾਹੀਦੀ ਹੈ।",
        "expected_level": "10th",
        "expected_skill": "carpentry",
        "expected_district": "Amritsar",
        "expected_pref": "job",
        "expected_months": 24,
    },
    {
        "lang": "or",
        "name": "Odia (Cuttack Electrical)",
        "text": "ନମସ୍କାର, ମୁଁ କଟକ ରେ ରହୁଛି, 10ମ ଶ୍ରେଣୀ ପାସ୍, 2 ବର୍ଷ ଇଲେକ୍ଟ୍ରିକାଲ୍ ୱାୟରିଂ କାମ କରିଛି, ଚାକିରି ଚାହୁଁଛି।",
        "expected_level": "10th",
        "expected_skill": "electrical",
        "expected_district": "Cuttack",
        "expected_pref": "job",
        "expected_months": 24,
    },
    {
        "lang": "en",
        "name": "Indian English (Warangal Solar)",
        "text": "Hello sir, I am 12th passout residing in Warangal. Having 2 years experience in solar panel installation and repair. Looking for private company job, ready to join skill course.",
        "expected_level": "12th",
        "expected_skill": "solar",
        "expected_district": "Warangal",
        "expected_pref": "job",
        "expected_months": 24,
        "expected_training": True,
    },
    {
        "lang": "hinglish",
        "name": "Hinglish (Bhopal Garage)",
        "text": "Sir mera naam amit hai, main Bhopal me rehta hu, 10th pass hu, 1 year se car aur bike repairing ka kaam kar raha hu, khud ka garage business start karna chahta hu.",
        "expected_level": "10th",
        "expected_skill": "automotive",
        "expected_district": "Bhopal",
        "expected_pref": "business",
        "expected_months": 12,
    },
]


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Test 1: Extraction on 12 Brand New Scenarios
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("case", NEW_12_INDIAN_SCENARIOS, ids=[c["name"] for c in NEW_12_INDIAN_SCENARIOS])
def test_new_scenarios_unstructured_extraction(case):
    extractor = LocalProfileExtractor()
    profile = extractor.extract(case["text"], language_code=case["lang"])

    assert profile.education.level == case["expected_level"]
    assert profile.education.status == "passed"
    assert case["expected_skill"] in profile.skills
    assert profile.location.district == case["expected_district"]
    assert profile.employment_preference == case["expected_pref"]
    if case.get("expected_months"):
        assert profile.experience
        assert profile.experience[0].duration_months == case["expected_months"]
    if "expected_training" in case:
        assert profile.training_willingness == case["expected_training"]


# ---------------------------------------------------------------------------
# Test 2: Audio Structural & Acoustical Integrity (All 12 Languages)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("case", NEW_12_INDIAN_SCENARIOS, ids=[c["name"] for c in NEW_12_INDIAN_SCENARIOS])
def test_all_12_languages_audio_wav_integrity(client, case):
    """Inspect WAV header, non-zero PCM energy, and duration > 1.5 seconds."""
    res = client.post("/tts/offline", json={"text": case["text"][:120], "language": case["lang"]})
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/wav"

    wav_bytes = res.content
    assert len(wav_bytes) > 50000

    # Parse WAV headers
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        channels = w.getnchannels()
        sampwidth = w.getsampwidth()
        framerate = w.getframerate()
        nframes = w.getnframes()
        duration = nframes / float(framerate)

        assert channels == 1, "Audio should be mono"
        assert sampwidth == 2, "Audio should be 16-bit PCM"
        assert framerate in (16000, 22050, 24000), f"Unexpected sample rate: {framerate}"
        assert duration >= 1.5, f"Audio duration too short: {duration:.2f}s"

        # Check acoustical energy (ensure audio is NOT digital silence)
        frames = w.readframes(min(nframes, framerate * 2))  # read first 2 seconds
        samples = struct.unpack(f"<{len(frames)//2}h", frames)
        max_amplitude = max(abs(s) for s in samples)
        rms = math.sqrt(sum(s*s for s in samples) / len(samples))
        assert max_amplitude > 500, "Audio is completely silent (flat line)"
        assert rms > 100, "Audio RMS energy too low"


# ---------------------------------------------------------------------------
# Test 3: Multi-Turn Conversation State Accumulation (3 Turns)
# ---------------------------------------------------------------------------
def test_multiturn_conversation_state_accumulation(client):
    """Verify that a 3-turn beneficiary dialogue accumulates facts without dropping prior slots."""
    # Turn 1: Beneficiary gives education and trade in Hindi
    r1 = client.post(
        "/conversation/offline",
        json={"text": "मैं 10वीं पास हूँ और दो साल से इलेक्ट्रीशियन का काम करता हूँ", "language_code": "hi"},
    ).json()

    prof1 = r1["profile"]
    assert prof1["education"]["level"] == "10th"
    assert "electrical" in prof1["skills"]
    assert prof1["location"]["district"] is None
    # Assistant should now ask for missing field (location or employment preference)
    assert r1["next_question"] is not None

    # Turn 2: Beneficiary gives location
    r2 = client.post(
        "/conversation/offline",
        json={"text": "मैं लखनऊ में रहता हूँ", "current_profile": prof1, "language_code": "hi"},
    ).json()

    prof2 = r2["profile"]
    # Verify prior facts were preserved
    assert prof2["education"]["level"] == "10th"
    assert "electrical" in prof2["skills"]
    assert prof2["location"]["district"] == "Lucknow"
    assert prof2["location"]["state"] == "Uttar Pradesh"

    # Turn 3: Beneficiary provides employment preference and willingness for training
    r3 = client.post(
        "/conversation/offline",
        json={
            "text": "मुझे प्राइवेट कंपनी में जॉब चाहिए और ट्रेनिंग करने को तैयार हूँ",
            "current_profile": prof2,
            "language_code": "hi",
            "include_recommendations": True,
        },
    ).json()

    prof3 = r3["profile"]
    assert prof3["education"]["level"] == "10th"
    assert "electrical" in prof3["skills"]
    assert prof3["location"]["district"] == "Lucknow"
    assert prof3["employment_preference"] == "job"
    assert prof3["training_willingness"] is True
    # Now all critical fields are present
    assert r3["ready_for_mapping"] is True
    assert len(r3["recommendations"]) > 0


# ---------------------------------------------------------------------------
# Test 4: Recommendation Engine Actual Database Querying
# ---------------------------------------------------------------------------
def test_recommendation_engine_finds_nsqf_qualifications(client):
    """Verify recommendation engine matches real NQR qualifications for extracted profile."""
    res = client.post(
        "/recommend",
        json={
            "profile": {
                "education": {"level": "10th", "status": "passed"},
                "skills": ["electrical"],
                "location": {"district": "Lucknow", "state": "Uttar Pradesh"},
                "employment_preference": "job",
                "training_willingness": True,
            }
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data.get("recommendations", [])) > 0
    first_rec = data["recommendations"][0]
    assert "qualification" in first_rec or "title" in first_rec or "job_role" in first_rec or "qualification_name" in first_rec


# ---------------------------------------------------------------------------
# Test 5: Indian Accent Phonetic & Edge-Case Robustness
# ---------------------------------------------------------------------------
def test_accent_phonetics_and_adversarial_turns():
    ex = LocalProfileExtractor()

    # Phonetic trade slips ("electraction", "frij ripair", "two wilar mechanic")
    p1 = ex.extract("I have 2 years experience in electraction and frij ac ripair in Hyderabad")
    assert "electrical" in p1.skills
    assert "refrigeration and ac" in p1.skills
    assert p1.location.district == "Hyderabad"

    # Explicit refusal of training
    p2 = ex.extract("10th pass, direct company job do, mujhe koi training nahi chahiye")
    assert p2.education.level == "10th"
    assert p2.training_willingness is False
    assert p2.employment_preference == "job"

    # Self-employment / swarozgar intent
    p3 = ex.extract("12th pass, welding work, main apna khud ka kaam karunga swarozgar")
    assert p3.education.level == "12th"
    assert "welding" in p3.skills
    assert p3.employment_preference == "self_employment"
