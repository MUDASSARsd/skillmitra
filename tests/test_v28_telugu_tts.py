from pathlib import Path
from backend.tts_local import LocalTTS


def test_project_local_auto_discovery(monkeypatch, tmp_path):
    # Exercise discovery with an explicit portable directory without requiring Piper.
    d = tmp_path / "voice"
    d.mkdir()
    model = d / "te_IN-padmavathi-medium.onnx"
    config = d / "te_IN-padmavathi-medium.onnx.json"
    model.write_bytes(b"model")
    config.write_text("{}", encoding="utf-8")
    monkeypatch.delenv("PIPER_TELUGU_MODEL", raising=False)
    monkeypatch.delenv("PIPER_TELUGU_CONFIG", raising=False)
    monkeypatch.setenv("ALLOW_EXTERNAL_MODEL_PATHS", "1")
    monkeypatch.setenv("PIPER_TELUGU_DIR", str(d))
    tts = LocalTTS()
    assert tts.telugu_model == model
    assert tts.telugu_config == config
    assert tts.discovery == "PIPER_TELUGU_DIR"


def test_explicit_env_still_supported(monkeypatch, tmp_path):
    model = tmp_path / "custom.onnx"
    config = tmp_path / "custom.json"
    model.write_bytes(b"x")
    config.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("ALLOW_EXTERNAL_MODEL_PATHS", "1")
    monkeypatch.setenv("PIPER_TELUGU_MODEL", str(model))
    monkeypatch.setenv("PIPER_TELUGU_CONFIG", str(config))
    tts = LocalTTS()
    assert tts.telugu_model == model
    assert tts.telugu_config == config
    assert tts.discovery == "external-environment"


def test_status_gives_actionable_setup_message(monkeypatch, tmp_path):
    monkeypatch.delenv("PIPER_TELUGU_MODEL", raising=False)
    monkeypatch.delenv("PIPER_TELUGU_CONFIG", raising=False)
    monkeypatch.setenv("PIPER_TELUGU_DIR", str(tmp_path / "missing"))
    tts = LocalTTS()
    monkeypatch.setattr(tts, "_piper_installed", lambda: True)
    monkeypatch.setattr(tts, "_espeak_ready", lambda: False)
    status = tts.status().as_dict()
    assert status["ready"] is False
    assert "SETUP_TELUGU_TTS.bat" in status["detail"]
