from pathlib import Path
from types import SimpleNamespace

from backend.tts_local import LocalTTS, _ESPEAK_VOICES

ROOT = Path(__file__).resolve().parents[1]
UI_LANGS = {"en", "hi", "te", "ta", "kn", "ml", "mr", "bn", "gu", "pa", "or"}


def test_espeak_fallback_covers_all_ui_languages():
    assert UI_LANGS.issubset(_ESPEAK_VOICES)
    assert _ESPEAK_VOICES["te"] == "te"
    assert _ESPEAK_VOICES["ta"] == "ta"
    assert _ESPEAK_VOICES["kn"] == "kn"
    assert _ESPEAK_VOICES["or"] == "or"


def test_offline_frontend_routes_every_language_to_backend():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "await playAudioResponse('/tts/offline',{text,language:code})" in js
    assert "run SETUP_OFFLINE_TTS.bat once" in js


def test_setup_script_is_included_and_uses_exact_winget_package():
    setup = (ROOT / "SETUP_OFFLINE_TTS.bat").read_text(encoding="utf-8")
    assert "eSpeak-NG.eSpeak-NG" in setup
    assert ".env file is read or changed" in setup


def test_espeak_synthesis_uses_language_voice(monkeypatch, tmp_path):
    fake_exe = tmp_path / "espeak-ng.exe"
    fake_exe.write_bytes(b"fake")
    tts = LocalTTS()
    tts.espeak_executable = fake_exe

    seen = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        out = Path(args[args.index("-w") + 1])
        # Minimal file length check in implementation only needs >44 bytes.
        out.write_bytes(b"RIFF" + b"0" * 100)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("backend.tts_local.subprocess.run", fake_run)
    out = tts._synthesize_espeak("నమస్తే", "te")
    try:
        assert "-v" in seen["args"]
        assert seen["args"][seen["args"].index("-v") + 1] == "te"
        assert out.exists()
    finally:
        out.unlink(missing_ok=True)


def test_status_marks_all_languages_ready_when_espeak_exists(monkeypatch, tmp_path):
    fake_exe = tmp_path / "espeak-ng.exe"
    fake_exe.write_bytes(b"fake")
    tts = LocalTTS()
    tts.espeak_executable = fake_exe
    monkeypatch.setattr(tts, "_piper_ready", lambda lang: False)
    status = tts.status().as_dict()
    assert status["espeak_ready"] is True
    for lang in UI_LANGS:
        assert status["languages"][lang]["ready"] is True
        assert status["languages"][lang]["engine"] == "espeak-ng"
