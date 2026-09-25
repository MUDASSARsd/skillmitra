from pathlib import Path

from backend.conversation.questions import QUESTIONS, SUPPORTED_LANGUAGES, _language_family
from backend.stt_local import INDIC_LANGUAGE_CODES

ROOT = Path(__file__).resolve().parents[1]

LANGS = {"en", "hi", "te", "ta", "kn", "ml", "mr", "bn", "gu", "pa", "or"}
INDIC_UI_LANGS = LANGS - {"en"}

def test_counter_questions_cover_all_supported_languages():
    assert LANGS.issubset(SUPPORTED_LANGUAGES)
    for field, table in QUESTIONS.items():
        for lang in LANGS:
            assert table.get(lang), f"missing {lang} translation for {field}"

def test_language_family_routes_all_supported_codes():
    for lang in LANGS:
        assert _language_family(lang) == lang
        assert _language_family(f"{lang}-IN") == lang
    assert _language_family("hinglish") == "hinglish"
    assert _language_family("xx") == "en"

def test_offline_indic_stt_can_route_every_added_indic_language():
    assert INDIC_UI_LANGS.issubset(INDIC_LANGUAGE_CODES)

def test_frontend_exposes_all_languages_and_speech_locales():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    for lang in LANGS:
        assert f'value="{lang}"' in html
        assert f"{lang}:" in js or f"'{lang}'" in js
    for locale in ("ta-IN", "kn-IN", "ml-IN", "mr-IN", "bn-IN", "gu-IN", "pa-IN", "or-IN"):
        assert locale in js

def test_nlu_prompts_advertise_new_languages():
    online = (ROOT / "backend" / "nlu" / "online_extractor.py").read_text(encoding="utf-8")
    offline = (ROOT / "backend" / "nlu" / "ollama_extractor.py").read_text(encoding="utf-8")
    for name in ("Tamil", "Kannada", "Malayalam", "Marathi", "Bengali", "Gujarati", "Punjabi", "Odia"):
        assert name in online
        assert name in offline
