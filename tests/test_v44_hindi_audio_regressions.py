from pathlib import Path

from backend.nlu.local_extractor import LocalProfileExtractor
from backend.models.beneficiary import BeneficiaryProfile

ROOT = Path(__file__).resolve().parents[1]


def test_hindi_electrician_asr_variant_is_not_lost():
    p = LocalProfileExtractor().extract_patch(
        "मेरा नाम मुदासिर है मैं दो साल से इलेक्ट्रेशन का काम कर रहा हूं",
        BeneficiaryProfile(),
        "hi",
    )
    assert "electrical" in p.skills
    assert p.experience and p.experience[0].duration_months == 24


def test_hindi_flow_moves_past_livelihood_after_10th():
    ex = LocalProfileExtractor()
    p = ex.extract("मैं दो साल से इलेक्ट्रेशन का काम कर रहा हूं", language_code="hi")
    p = ex.extract("10वीं कक्षा", p, "hi")
    assert p.education.level == "10th"
    assert "electrical" in p.skills


def test_offline_tts_browser_wav_is_primary_and_windows_is_fallback():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    start = js.index("async function speak(text)")
    end = js.index("async function reportTTSAvailability()", start)
    block = js[start:end]
    wav = block.index("playAudioResponse('/tts/offline'")
    direct = block.index("/tts/offline/play-local")
    assert wav < direct
    assert "ttsAudioPrimed" in js


def test_windows_playback_is_verified_before_success():
    code = (ROOT / "backend" / "tts_local.py").read_text(encoding="utf-8")
    assert "winsound.SND_FILENAME | winsound.SND_ASYNC" in code
    assert "jeevikamitra-tts-cleanup" in code
