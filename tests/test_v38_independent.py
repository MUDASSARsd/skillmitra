from pathlib import Path


def test_stt_ignores_external_paths_by_default(monkeypatch, tmp_path):
    fake = tmp_path / 'old-project'
    monkeypatch.setenv('ALLOW_EXTERNAL_MODEL_PATHS', '0')
    monkeypatch.setenv('PARAKEET_MODEL_DIR', str(fake / 'parakeet'))
    monkeypatch.setenv('WHISPER_CPP_BIN', str(fake / 'whisper.exe'))
    monkeypatch.setenv('WHISPER_MODEL_PATH', str(fake / 'model.bin'))
    from backend.stt_local import LocalSTT
    stt = LocalSTT()
    assert stt.parakeet_dir is None
    assert stt.whisper_bin is None
    assert stt.whisper_model is None
    assert 'models' in str(stt.faster_whisper_dir)


def test_tts_does_not_use_old_documents_folder(monkeypatch, tmp_path):
    monkeypatch.setenv('ALLOW_EXTERNAL_MODEL_PATHS', '0')
    monkeypatch.setenv('PIPER_TELUGU_MODEL', str(tmp_path / 'old' / 'te.onnx'))
    from backend.tts_local import LocalTTS
    tts = LocalTTS()
    assert tts.telugu_discovery in {'project-local', 'not-found'}
    assert 'indic_asr_test' not in str(tts.telugu_model)


def test_render_blueprint_uses_cloud_runtime():
    root = Path(__file__).resolve().parents[1]
    text = (root / 'render.yaml').read_text(encoding='utf-8')
    assert 'SKILLMITRA_RUNTIME' in text
    assert 'value: cloud' in text
    assert 'GEMINI_API_KEY' in text
    assert 'sync: false' in text


def test_independent_setup_exists():
    root = Path(__file__).resolve().parents[1]
    assert (root / 'SETUP_INDEPENDENT_LOCAL.bat').is_file()
    assert (root / 'data' / 'nqr_database.db').is_file()
    assert (root / 'data' / 'nqr_semantic_embeddings.npz').is_file()
