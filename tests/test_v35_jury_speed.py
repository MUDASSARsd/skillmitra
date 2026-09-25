from pathlib import Path

from backend.nlu.local_extractor import LocalProfileExtractor
from backend.nlu.ollama_extractor import HybridOfflineProfileExtractor, OllamaProfileExtractor

ROOT = Path(__file__).resolve().parents[1]


def test_start_hybrid_is_fast_and_disables_reload():
    bat = (ROOT / 'START_HYBRID.bat').read_text(encoding='utf-8')
    assert 'call "%~dp0PREPARE_JURY_MIC.bat"' not in bat
    assert '--reload' not in bat
    assert (ROOT / 'PREPARE_JURY_MIC.bat').is_file()


def test_fast_mic_setup_uses_quality_multilingual_model():
    setup = (ROOT / 'setup_offline_stt.py').read_text(encoding='utf-8')
    assert 'Systran/faster-whisper-small' in setup
    stt = (ROOT / 'backend' / 'stt_local.py').read_text(encoding='utf-8')
    assert 'faster-whisper-tiny' in stt
    assert 'def warmup' in stt


def test_simple_offline_jury_answer_skips_ollama(monkeypatch):
    def should_not_run(*args, **kwargs):
        raise AssertionError('Ollama should not run for a simple recognised jury answer')

    monkeypatch.setattr(OllamaProfileExtractor, 'extract', should_not_run)
    ex = HybridOfflineProfileExtractor(fallback=LocalProfileExtractor())
    p = ex.extract('I completed my 10th class and worked as an electrician for 1 year', language_code='en')
    assert p.education.level == '10th'
    assert 'electrical' in p.skills
    assert p.experience and p.experience[0].duration_months == 12
    assert ex.last_model_used == 'rules-fastpath'


def test_online_voice_uses_cloud_recorder_not_local_stt():
    js = (ROOT / 'frontend' / 'app.js').read_text(encoding='utf-8')
    assert "startOfflineRecording('online')" in js
    online_block=js[js.index('if(!offline){'):js.index('// Offline mode:', js.index('if(!offline){'))]
    assert 'refreshOfflineSTT()' not in online_block
