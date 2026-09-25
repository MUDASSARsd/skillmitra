from pathlib import Path

from backend.nlu.local_extractor import LocalProfileExtractor
from backend.nlu.online_extractor import HybridOnlineProfileExtractor, OnlineProfileExtractor

ROOT = Path(__file__).resolve().parents[1]


def test_online_voice_never_waits_for_local_whisper():
    js=(ROOT/'frontend'/'app.js').read_text(encoding='utf-8')
    online_block=js[js.index('if(!offline){'):js.index('// Offline mode:', js.index('if(!offline){'))]
    assert "startOfflineRecording('online')" in online_block
    assert 'refreshOfflineSTT()' not in online_block
    assert "online-local-first" not in online_block


def test_online_stt_uses_single_inline_audio_path():
    src=(ROOT/'backend'/'stt_online.py').read_text(encoding='utf-8')
    assert '_transcribe_dedicated_inline' in src
    assert 'base64.b64encode(audio)' in src
    assert 'gemini-3.5-transcribe-inline' in src


def test_online_extractor_default_is_flash_lite_and_minimal_thinking():
    ex=OnlineProfileExtractor(api_key='x')
    assert ex.model_name == 'gemini-3.5-flash-lite'
    src=(ROOT/'backend'/'nlu'/'online_extractor.py').read_text(encoding='utf-8')
    assert "'thinkingLevel':'minimal'" in src


def test_simple_online_jury_answer_skips_cloud_model():
    def should_not_run(*args, **kwargs):
        raise AssertionError('Gemini should not run for simple understood jury input')
    ex=HybridOnlineProfileExtractor(api_key='x', api_caller=should_not_run)
    p=ex.extract('I completed 10th and worked as electrician for 1 year', language_code='en')
    assert p.education.level == '10th'
    assert p.experience and p.experience[0].duration_months == 12
    assert ex.last_mode == 'online_fast_rules'


def test_launcher_does_not_block_on_prepare_mic():
    bat=(ROOT/'START_HYBRID.bat').read_text(encoding='utf-8')
    assert 'call "%~dp0PREPARE_JURY_MIC.bat"' not in bat
