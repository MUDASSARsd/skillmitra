from pathlib import Path
from types import SimpleNamespace

from backend.stt_local import LocalSTT, _SHERPA_INDIC_UI_LANGS
from backend.tts_local import LocalTTS

ROOT = Path(__file__).resolve().parents[1]


def test_v42_indic_first_languages_cover_ui():
    assert {"hi","te","ta","kn","ml","mr","bn","gu","pa","or"}.issubset(set(_SHERPA_INDIC_UI_LANGS))


def test_v42_transcribe_prefers_sherpa_for_telugu(monkeypatch, tmp_path):
    stt = LocalSTT()
    wav = tmp_path / "a.wav"
    monkeypatch.setattr(stt, "validate_wav", lambda _: (1,2,16000))
    monkeypatch.setattr(stt, "_sherpa_model_ready", lambda lang: lang == "te")
    monkeypatch.setattr(stt, "_transcribe_sherpa", lambda path, lang: "నేను పదో తరగతి చదివాను")
    text, engine = stt.transcribe(wav, "te")
    assert text.startswith("నేను")
    assert engine == "sherpa-indicconformer"


def test_v42_core_setup_downloads_indic_models_not_generic_whisper():
    bat = (ROOT / "PREPARE_JURY_MIC.bat").read_text(encoding="utf-8")
    py = (ROOT / "setup_indic_sherpa.py").read_text(encoding="utf-8")
    assert "setup_indic_sherpa.py" in bat
    assert "sherpa-onnx" in bat
    assert 'CORE = ["en", "hi", "te", "ta", "hinglish"]' in py
    assert "parismitaglobalsolutions/indicconformer-sherpa-onnx" in py


def test_v42_full_pack_script_exists():
    bat = (ROOT / "SETUP_ALL_OFFLINE_LANGUAGES.bat").read_text(encoding="utf-8")
    assert "setup_indic_sherpa.py --all" in bat
    assert "LARGE one-time download" in bat


def test_v42_offline_tts_backend_precedes_browser_voice():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    speak = js[js.index("async function speak(text){"):js.index("async function reportTTSAvailability()") ]
    offline_branch = speak.index("if($('mode')?.value==='offline')")
    backend = speak.index("await playAudioResponse('/tts/offline',{text,language:code})")
    browser = speak.index("if('speechSynthesis' in window && voice)")
    assert offline_branch < backend < browser


def test_v42_tts_passes_explicit_espeak_data_path(monkeypatch, tmp_path):
    exe_dir = tmp_path / "eSpeak NG"
    (exe_dir / "espeak-ng-data").mkdir(parents=True)
    exe = exe_dir / "espeak-ng.exe"
    exe.write_bytes(b"fake")
    tts = LocalTTS()
    tts.espeak_executable = exe
    tts.espeak_data_parent = exe_dir
    seen = {}
    def fake_run(args, **kwargs):
        seen["args"] = args
        seen["env"] = kwargs.get("env", {})
        out = Path(args[args.index("-w") + 1])
        out.write_bytes(b"RIFF" + b"0"*100)
        return SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr("backend.tts_local.subprocess.run", fake_run)
    out = tts._synthesize_espeak("నమస్తే", "te")
    try:
        assert any(str(x).startswith("--path=") for x in seen["args"])
        assert seen["env"].get("ESPEAK_DATA_PATH") == str(exe_dir)
    finally:
        out.unlink(missing_ok=True)


def test_v42_frontend_checks_selected_language_engine():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "offlineSTTStatus?.language_engines?.[lang]" in js
    assert "SETUP_ALL_OFFLINE_LANGUAGES.bat" in js
