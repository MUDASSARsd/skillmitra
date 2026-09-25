"""Regression test for Hindi and Telugu multi-fact stories during conversation and STT normalization.

Prevents the bug where telling a complete story in Hindi or Telugu:
- was truncated to just "10th class" / "10वीं कक्षा" / "పదో తరగతి" by ASR contextual normalization, or
- only extracted education while dropping skills, experience, location, and employment preference.
"""
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.nlu.local_extractor import LocalProfileExtractor, normalize_contextual_transcript
from backend.models.beneficiary import BeneficiaryProfile


def test_stt_normalization_preserves_full_stories():
    """Ensure multi-fact stories in Hindi, Telugu, English are never truncated to just an education label."""
    stories = [
        ("hi", "मैं 10वीं पास हूँ और 2 साल से इलेक्ट्रीशियन का काम कर रहा हूँ मुझे हैदराबाद में नौकरी चाहिए"),
        ("hi", "मैंने 10th पास किया है और मैं प्लम्बर का काम करता हूँ मुझे 1 साल का अनुभव है और मैं जॉब चाहता हूँ"),
        ("hi", "10 class pass hu aur electrical wiring ka kaam janta hu 2 saal se hyderabad me job chahiye"),
        ("te", "నేను 10వ తరగతి పాస్ అయ్యాను 2 సంవత్సరాలు ఎలక్ట్రీషియన్ పని చేశాను హైదరాబాద్ లో జాబ్ కావాలి"),
        ("te", "నేను టెన్త్ క్లాస్ పాస్ అయ్యాను 2 ఏళ్ళు ఎలక్ట్రికల్ పని చేశాను హైదరాబాద్ లో ఉద్యోగం కావాలి"),
        ("te", "10th class pass ayyanu electrician work 2 years hyderabad lo job kavali"),
        ("en", "I passed 10th class and I have 2 years of experience as an electrician and I want a job in Hyderabad"),
    ]
    for lang, story in stories:
        norm = normalize_contextual_transcript(story, expected_field="education", language_code=lang)
        assert norm == story, f"Failed for [{lang}]: '{story}' was corrupted to '{norm}'"


def test_stt_normalization_still_canonicalizes_short_education_replies():
    """Ensure short isolated education answers remain canonicalized to standard grades."""
    assert normalize_contextual_transcript("Tend the glass", "education", "en") == "10th class"
    assert normalize_contextual_transcript("I have completed my teninth", "education", "en") == "10th class"
    assert normalize_contextual_transcript("टैेंथ क्लास", "education", "hi") == "10वीं कक्षा"
    assert normalize_contextual_transcript("పదో తరగతి", "education", "te") == "పదో తరగతి"


def test_hindi_story_extracts_all_profile_fields():
    ext = LocalProfileExtractor()
    story = "मैं 10वीं पास हूँ और 2 साल से इलेक्ट्रीशियन का काम कर रहा हूँ मुझे हैदराबाद में नौकरी चाहिए"
    p = ext.extract(story, language_code="hi")
    assert p.education.level == "10th"
    assert "electrical" in p.skills
    assert p.experience and p.experience[0].domain == "electrical"
    assert p.experience[0].duration_months == 24
    assert p.location.district == "Hyderabad"
    assert p.employment_preference == "job"


def test_telugu_story_extracts_all_profile_fields():
    ext = LocalProfileExtractor()
    story = "నేను 10వ తరగతి పాస్ అయ్యాను 2 సంవత్సరాలు ఎలక్ట్రీషియన్ పని చేశాను హైదరాబాద్ లో జాబ్ కావాలి"
    p = ext.extract(story, language_code="te")
    assert p.education.level == "10th"
    assert "electrical" in p.skills
    assert p.experience and p.experience[0].domain == "electrical"
    assert p.experience[0].duration_months == 24
    assert p.location.district == "Hyderabad"
    assert p.employment_preference == "job"


def test_telugu_plumbing_and_carpentry_stories():
    ext = LocalProfileExtractor()
    plumb_story = "నేను 10వ తరగతి పూర్తి చేశాను నాకు ప్లంబింగ్ పని వచ్చు 1 సంవత్సరం అనుభవం ఉంది జాబ్ కావాలి"
    p1 = ext.extract(plumb_story, language_code="te")
    assert p1.education.level == "10th"
    assert "plumbing" in p1.skills
    assert p1.experience and p1.experience[0].duration_months == 12
    assert p1.employment_preference == "job"

    carp_story = "నేను 10వ తరగతి చదివాను నాకు కార్పెంటర్ పని వచ్చు 3 సంవత్సరాల అనుభవం ఉంది సొంత షాప్ పెట్టాలనుకుంటున్నాను"
    p2 = ext.extract(carp_story, language_code="te")
    assert p2.education.level == "10th"
    assert "carpentry" in p2.skills
    assert p2.experience and p2.experience[0].duration_months == 36
    assert p2.employment_preference == "business"


def test_offline_conversation_endpoint_processes_full_telugu_story():
    client = TestClient(app)
    payload = {
        "text": "నేను 10వ తరగతి పాస్ అయ్యాను 2 సంవత్సరాలు ఎలక్ట్రీషియన్ పని చేశాను హైదరాబాద్ లో జాబ్ కావాలి",
        "current_profile": None,
        "language_code": "te",
        "include_recommendations": True,
        "top_k": 3
    }
    resp = client.post("/conversation/offline", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    prof = data["profile"]
    assert prof["education"]["level"] == "10th"
    assert "electrical" in prof["skills"]
    assert prof["experience"] and prof["experience"][0]["duration_months"] == 24
    assert prof["location"]["district"] == "Hyderabad"
    assert prof["employment_preference"] == "job"
