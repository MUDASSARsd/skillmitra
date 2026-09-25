from fastapi.testclient import TestClient
from backend.api.app import app
from backend.nlu.local_extractor import LocalProfileExtractor
from backend.models.beneficiary import BeneficiaryProfile, Education, Experience


def test_local_extractor_does_not_mutate_caller_profile():
    base = BeneficiaryProfile(
        education=Education(level='10th', status='passed'),
        skills=['electrical'],
        experience=[Experience(domain='electrical', duration_months=12)],
        language='hi',
    )
    before = base.model_dump()
    out = LocalProfileExtractor().extract('नौकरी', base, 'hi')
    assert base.model_dump() == before
    assert out.employment_preference == 'job'


def test_offline_conversation_never_requires_ollama_for_core_flow(monkeypatch):
    # Even if a stale user setting disables an old optional fallback flag, the
    # endpoint must keep working with deterministic local extraction.
    monkeypatch.setenv('OLLAMA_ALLOW_RULE_FALLBACK', '0')
    c = TestClient(app)
    r = c.post('/conversation/offline', json={
        'text': '10th pass, 2 saal electrical wiring ka kaam kiya, job chahiye',
        'language_code': 'hinglish',
        'include_recommendations': True,
    })
    assert r.status_code == 200
    d = r.json()
    assert d['profile']['education']['level'] == '10th'
    assert d['profile']['employment_preference'] == 'job'


def test_exact_hindi_jury_flow_does_not_repeat_education():
    c = TestClient(app)
    r = c.post('/conversation', json={
        'text': 'मेरा नाम सैयद मुदासिर है, मैं इलेक्ट्रीशियन का काम करता हूँ, एक साल से, मैं 10 वीं कक्षा तक पढ़ा हूँ।',
        'language_code': 'hi',
    })
    assert r.status_code == 200
    d = r.json()
    assert d['profile']['education']['level'] == '10th'
    assert d['profile']['experience'][0]['duration_months'] == 12
    assert 'education' not in d['missing_critical']
    assert d['next_question'] and ('नौकरी' in d['next_question'] or 'naukri' in d['next_question'].lower())


def test_exact_hindi_ambiguous_job_reply_gets_clarifier_without_guessing():
    c = TestClient(app)
    profile = BeneficiaryProfile(
        education=Education(level='10th', status='passed'),
        skills=['electrical'],
        experience=[Experience(domain='electrical', duration_months=12)],
        language='hi',
    )
    r = c.post('/conversation', json={
        'text': 'हां मैं चाहता',
        'current_profile': profile.model_dump(),
        'language_code': 'hi',
    })
    assert r.status_code == 200
    d = r.json()
    assert d['profile']['employment_preference'] is None
    assert 'नौकरी' in d['next_question']
    assert 'स्वरोज़गार' in d['next_question']
    assert 'बिजनेस' in d['next_question']


def test_offline_deterministic_core_covers_all_advertised_ui_languages():
    samples = {
        'ta': 'நான் 10ஆம் வகுப்பு முடித்தேன். ஒரு வருடம் electrician வேலை செய்தேன். எனக்கு வேலை வேண்டும்.',
        'kn': 'ನಾನು 10ನೇ ತರಗತಿ ಪಾಸ್ ಆಗಿದ್ದೇನೆ. ಒಂದು ವರ್ಷ electrician ಕೆಲಸ ಮಾಡಿದ್ದೇನೆ. ನನಗೆ ಉದ್ಯೋಗ ಬೇಕು.',
        'ml': 'ഞാൻ 10ാം ക്ലാസ് പാസായി. ഒരു വർഷം electrician ആയി ജോലി ചെയ്തു. എനിക്ക് ജോലി വേണം.',
        'mr': 'मी 10वी पास आहे. एक वर्ष electrician म्हणून काम केले. मला नोकरी हवी आहे.',
        'bn': 'আমি 10ম শ্রেণি পাশ করেছি। এক বছর electrician হিসেবে কাজ করেছি। আমি চাকরি চাই।',
        'gu': 'હું 10મું ધોરણ પાસ છું. એક વર્ષ electrician તરીકે કામ કર્યું. મને નોકરી જોઈએ.',
        'pa': 'ਮੈਂ 10ਵੀਂ ਕਲਾਸ ਪਾਸ ਕੀਤੀ ਹੈ। ਇੱਕ ਸਾਲ electrician ਦਾ ਕੰਮ ਕੀਤਾ। ਮੈਨੂੰ ਨੌਕਰੀ ਚਾਹੀਦੀ ਹੈ।',
        'or': 'ମୁଁ 10ମ ଶ୍ରେଣୀ ପାସ୍ କରିଛି। ଏକ ବର୍ଷ electrician କାମ କରିଛି। ମୁଁ ଚାକିରି ଚାହୁଁଛି।',
    }
    ex = LocalProfileExtractor()
    for lang, text in samples.items():
        p = ex.extract(text, language_code=lang)
        assert p.education.level == '10th', lang
        assert p.education.status == 'passed', lang
        assert 'electrical' in p.skills, lang
        assert p.experience and p.experience[0].duration_months == 12, lang
        assert p.employment_preference == 'job', lang


def test_system_readiness_does_not_make_offline_core_depend_on_microphone(monkeypatch):
    import importlib
    app_module = importlib.import_module('backend.api.app')

    class FakeSTT:
        def status(self):
            class S:
                def as_dict(self):
                    return {'ready': False}
            return S()

    monkeypatch.setattr(app_module, 'LocalSTT', FakeSTT)
    c = TestClient(app)
    r = c.get('/system/readiness')
    assert r.status_code == 200
    d = r.json()
    assert d['offline_core_ready'] is True
    assert d['offline_voice_ready'] is False


def test_offline_nlu_status_reports_rules_ready_even_without_ollama(monkeypatch):
    import importlib
    app_module = importlib.import_module('backend.api.app')
    monkeypatch.setattr(app_module.OllamaProfileExtractor, 'status', lambda self: {'ready': False, 'detail': 'not running'})
    c = TestClient(app)
    d = c.get('/nlu/offline/status').json()
    assert d['ready'] is True
    assert d['ollama']['ready'] is False


def test_offline_full_three_turn_jury_flow_all_ui_languages():
    cases = {
        'en': ('I completed 10th. I worked as an electrician for one year. I want a job.', 'Hyderabad', 'yes'),
        'hi': ('मैं 10वीं पास हूँ। एक साल से इलेक्ट्रीशियन का काम करता हूँ। मुझे नौकरी चाहिए।', 'हैदराबाद', 'हाँ'),
        'hinglish': ('Main 10th pass hoon. Ek saal se electrician ka kaam karta hoon. Job chahiye.', 'Hyderabad', 'haan'),
        'te': ('నేను 10వ తరగతి చదివాను. ఒక సంవత్సరం ఎలక్ట్రీషియన్ పని చేశాను. ఉద్యోగం కావాలి.', 'హైదరాబాద్', 'అవును'),
        'ta': ('நான் 10ஆம் வகுப்பு முடித்தேன். ஒரு வருடம் எலக்ட்ரீஷியன் வேலை செய்தேன். எனக்கு வேலை வேண்டும்.', 'ஹைதராபாத்', 'ஆம்'),
        'kn': ('ನಾನು 10ನೇ ತರಗತಿ ಪಾಸ್ ಆಗಿದ್ದೇನೆ. ಒಂದು ವರ್ಷ ಎಲೆಕ್ಟ್ರಿಷಿಯನ್ ಕೆಲಸ ಮಾಡಿದ್ದೇನೆ. ನನಗೆ ಉದ್ಯೋಗ ಬೇಕು.', 'ಹೈದರಾಬಾದ್', 'ಹೌದು'),
        'ml': ('ഞാൻ 10ാം ക്ലാസ് പാസായി. ഒരു വർഷം ഇലക്ട്രീഷ്യൻ ആയി ജോലി ചെയ്തു. എനിക്ക് ജോലി വേണം.', 'ഹൈദരാബാദ്', 'അതെ'),
        'mr': ('मी 10वी पास आहे. एक वर्ष इलेक्ट्रीशियन म्हणून काम केले. मला नोकरी हवी आहे.', 'हैदराबाद', 'हो'),
        'bn': ('আমি 10ম শ্রেণি পাশ করেছি। এক বছর ইলেকট্রিশিয়ান হিসেবে কাজ করেছি। আমি চাকরি চাই।', 'হায়দরাবাদ', 'হ্যাঁ'),
        'gu': ('હું 10મું ધોરણ પાસ છું. એક વર્ષ ઇલેક્ટ્રિશિયન તરીકે કામ કર્યું. મને નોકરી જોઈએ.', 'હૈદરાબાદ', 'હા'),
        'pa': ('ਮੈਂ 10ਵੀਂ ਕਲਾਸ ਪਾਸ ਕੀਤੀ ਹੈ। ਇੱਕ ਸਾਲ ਇਲੈਕਟ੍ਰੀਸ਼ੀਅਨ ਦਾ ਕੰਮ ਕੀਤਾ। ਮੈਨੂੰ ਨੌਕਰੀ ਚਾਹੀਦੀ ਹੈ।', 'ਹੈਦਰਾਬਾਦ', 'ਹਾਂ'),
        'or': ('ମୁଁ 10ମ ଶ୍ରେଣୀ ପାସ୍ କରିଛି। ଏକ ବର୍ଷ ଇଲେକ୍ଟ୍ରିସିଆନ କାମ କରିଛି। ମୁଁ ଚାକିରି ଚାହୁଁଛି।', 'ହାଇଦ୍ରାବାଦ', 'ହଁ'),
    }
    c = TestClient(app)
    for lang, turns in cases.items():
        profile = None
        final = None
        for text in turns:
            r = c.post('/conversation/offline', json={
                'text': text,
                'current_profile': profile,
                'language_code': lang,
                'include_recommendations': True,
                'top_k': 3,
            })
            assert r.status_code == 200, (lang, r.text)
            final = r.json()
            profile = final['profile']
        assert final['ready_for_mapping'] is True, lang
        assert final['missing_critical'] == [], lang
        assert len(final['recommendations']) > 0, lang


def test_frontend_assets_are_versioned_to_avoid_stale_deploy_cache():
    import re
    from pathlib import Path
    html = (Path(__file__).resolve().parents[1] / 'frontend' / 'index.html').read_text(encoding='utf-8')
    assert re.search(r'/ui/app\.js\?v=\d+', html) is not None
    assert re.search(r'/ui/styles\.css\?v=\d+', html) is not None

