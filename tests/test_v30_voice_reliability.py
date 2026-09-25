from pathlib import Path

from backend.tts_online import ONLINE_VOICES, OnlineTTS

ROOT = Path(__file__).resolve().parents[1]
LANGS = {"en", "hi", "te", "ta", "kn", "ml", "mr", "bn", "gu", "pa", "or"}


def test_online_tts_has_all_ui_languages():
    assert LANGS.issubset(ONLINE_VOICES)
    assert ONLINE_VOICES["te"].startswith("te-IN-")
    assert ONLINE_VOICES["ta"].startswith("ta-IN-")
    assert ONLINE_VOICES["kn"].startswith("kn-IN-")


def test_online_tts_status_never_requires_env():
    status = OnlineTTS().status().as_dict()
    assert status["engine"] == "edge-tts"
    assert LANGS.issubset(set(status["supported_languages"]))


def test_frontend_separates_voice_status_from_mode_status():
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '<span id="voiceStatus">Voice ready.</span> <span id="voiceModeText">' in html
    assert '<span id="voiceStatus"><span id="voiceModeText">' not in html


def test_offline_mic_has_browser_on_device_fallback():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "SpeechRecognitionAPI.available" in js
    assert "SpeechRecognitionAPI.install" in js
    assert "processLocally:true" in js
    assert "await startBrowserRecognition(true)" in js


def test_online_tts_is_not_routed_through_piper_first():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    # V42 intentionally routes Offline mode to the local backend first, while
    # Online mode still has its own /tts/online branch and only a local fallback.
    assert "if($('mode')?.value==='offline')" in js
    assert "await playAudioResponse('/tts/online',{text,language:code})" in js
    assert "await playAudioResponse('/tts/offline',{text,language:localPiperLang})" in js


def test_edge_tts_dependency_is_declared():
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "edge-tts" in req


def test_portable_offline_stt_setup_is_included():
    assert (ROOT / "SETUP_OFFLINE_STT.bat").is_file()
    setup = (ROOT / "setup_offline_stt.py").read_text(encoding="utf-8")
    stt = (ROOT / "backend" / "stt_local.py").read_text(encoding="utf-8")
    assert "Systran/faster-whisper-small" in setup
    assert "faster-whisper-base" in stt
    assert "faster-whisper" in stt
