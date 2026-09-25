import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.conversation.session import ConversationManager
from backend.models.beneficiary import BeneficiaryProfile, Education, Experience, Location
from backend.nlu.local_extractor import LocalProfileExtractor
from backend.stt_local import LocalSTT

ROOT = Path(__file__).resolve().parents[1]


def ready_profile(lang='te'):
    return BeneficiaryProfile(
        education=Education(level='10th', status='passed'),
        skills=['electrical'],
        experience=[Experience(domain='electrical', duration_months=12)],
        employment_preference='job',
        location=Location(district='Hyderabad', state='Telangana'),
        training_willingness=None,
        language=lang,
    )


@pytest.mark.parametrize('text', [
    'సిద్ధంగా ఉన్నా',
    'సిద్దంగా ఉన్నా',
    'సిద్ధంగా ఉన్నాను',
    'రెడీ',
])
def test_telugu_training_willingness_real_user_phrases(text):
    turn = ConversationManager(LocalProfileExtractor()).process(text, ready_profile('te'), 'te')
    assert turn.profile.training_willingness is True
    assert turn.next_question is None
    assert turn.completeness.ready_for_mapping is True


@pytest.mark.parametrize('lang,text', [
    ('ta', 'தயாராக இருக்கிறேன்'),
    ('kn', 'ಸಿದ್ಧವಾಗಿದ್ದೇನೆ'),
    ('ml', 'തയ്യാറാണ്'),
    ('mr', 'तयार आहे'),
    ('bn', 'প্রস্তুত আছি'),
    ('gu', 'તૈયાર છું'),
    ('pa', 'ਤਿਆਰ ਹਾਂ'),
    ('or', 'ପ୍ରସ୍ତୁତ ଅଛି'),
])
def test_other_ui_languages_training_yes(text, lang):
    p = ready_profile(lang)
    turn = ConversationManager(LocalProfileExtractor()).process(text, p, lang)
    assert turn.profile.training_willingness is True, lang
    assert turn.next_question is None, lang


def test_selected_telugu_language_cannot_switch_counter_question_to_hinglish():
    p = ready_profile('hinglish')  # deliberately stale/wrong profile language
    p.training_willingness = None
    turn = ConversationManager(LocalProfileExtractor()).process('తెలియదు', p, 'te')
    assert turn.profile.language == 'te'
    assert turn.next_question.startswith('మీ పని లక్ష్యానికి')
    assert 'Agar ' not in turn.next_question


def test_offline_endpoint_swallows_malformed_optional_llm_and_uses_rules(monkeypatch):
    import importlib
    app_module = importlib.import_module('backend.api.app')

    class BrokenManager:
        def process(self, *args, **kwargs):
            raise json.JSONDecodeError('Unterminated string', '"abc', 1)

    monkeypatch.setattr(app_module, '_OFFLINE_MANAGER', BrokenManager())
    c = TestClient(app)
    r = c.post('/conversation/offline', json={
        'text': 'I completed 10th and worked as an electrician for 2 years in Hyderabad. I want a job.',
        'language_code': 'en',
        'include_recommendations': False,
    })
    assert r.status_code == 200
    d = r.json()
    assert 'Unterminated string' not in r.text
    assert d['profile']['education']['level'] == '10th'
    assert d['profile']['employment_preference'] == 'job'
    assert d['profile']['location']['district'] == 'Hyderabad'


def test_wrong_script_telugu_asr_result_is_rejected_instead_of_auto_sent():
    with pytest.raises(RuntimeError):
        LocalSTT._script_guard('ndon samatra vandali ka kishan panchis mernu', 'te')
    # Native Telugu and Hinglish remain allowed.
    LocalSTT._script_guard('నేను హైదరాబాద్ లో ఉంటాను', 'te')
    LocalSTT._script_guard('mai electrician ka kaam karta hu', 'hinglish')


def test_v41_prefers_small_whisper_and_independent_setup_installs_tts():
    stt_code = (ROOT / 'backend' / 'stt_local.py').read_text(encoding='utf-8')
    setup = (ROOT / 'setup_offline_stt.py').read_text(encoding='utf-8')
    independent = (ROOT / 'SETUP_INDEPENDENT_LOCAL.bat').read_text(encoding='utf-8')
    prep = (ROOT / 'PREPARE_JURY_MIC.bat').read_text(encoding='utf-8')
    assert 'self.faster_whisper_base_dir' in stt_code
    assert 'Systran/faster-whisper-small' in setup
    assert 'call SETUP_OFFLINE_TTS.bat' in independent
    assert 'setup_indic_sherpa.py' in prep
    assert 'sherpa-onnx' in prep


def test_frontend_keeps_audio_alive_and_awaits_tts():
    js = (ROOT / 'frontend' / 'app.js').read_text(encoding='utf-8')
    assert 'let activeAudio = null;' in js
    assert 'activeAudio=audio' in js
    assert 'await speak(d.next_question)' in js
