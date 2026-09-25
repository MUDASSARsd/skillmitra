from pathlib import Path
from unittest.mock import patch

from backend.stt_local import LocalSTT

ROOT = Path(__file__).resolve().parents[1]


def test_indic_readiness_does_not_mean_dependencies_only():
    stt = LocalSTT()
    stt.indic_model = "definitely/not/cached"
    with patch("backend.stt_local.importlib.util.find_spec", return_value=object()):
        with patch("huggingface_hub.try_to_load_from_cache", return_value=None):
            assert stt._indic_ready() is False


def test_frontend_prefers_local_multilingual_stt_for_online_indic():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "online-local-first" in js
    assert "Fast local multilingual transcription complete" in js
    assert "SETUP_FAST_MULTILINGUAL_MIC.bat" in js


def test_setup_alias_exists():
    bat = ROOT / "SETUP_FAST_MULTILINGUAL_MIC.bat"
    assert bat.is_file()
    text = bat.read_text(encoding="utf-8")
    assert "PREPARE_JURY_MIC.bat" in text
    assert "does NOT read or modify .env" in text
