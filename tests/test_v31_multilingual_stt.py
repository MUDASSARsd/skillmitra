from pathlib import Path

from backend.stt_online import OnlineSTT, _has_unexpected_arabic_script

ROOT = Path(__file__).resolve().parents[1]


class FakeResponse:
    def __init__(self, status=200, json_data=None, headers=None, text=""):
        self.status_code = status
        self._json = json_data or {}
        self.headers = headers or {}
        self.text = text
        self.ok = 200 <= status < 300

    def json(self):
        return self._json


class FakeSession:
    def __init__(self, transcript="मैं 1 साल से electrician का काम करता हूँ।"):
        self.transcript = transcript
        self.posts = []
        self.deleted = []

    def post(self, url, **kwargs):
        self.posts.append((url, kwargs))
        if "/upload/v1beta/files" in url:
            return FakeResponse(headers={"x-goog-upload-url": "https://upload.example/session"})
        if url == "https://upload.example/session":
            return FakeResponse(json_data={"file": {"uri": "https://files.example/audio", "name": "files/abc"}})
        if url.endswith("/v1beta/interactions"):
            return FakeResponse(json_data={"output_text": self.transcript})
        raise AssertionError(f"unexpected POST {url}")

    def delete(self, url, **kwargs):
        self.deleted.append((url, kwargs))
        return FakeResponse()


def test_hindi_and_english_are_both_hinted_for_code_mixing():
    assert OnlineSTT._language_codes("hi") == ["hi-IN", "en-IN"]
    assert OnlineSTT._language_codes("hinglish") == ["hi-IN", "en-IN"]


def test_telugu_and_english_are_both_hinted():
    assert OnlineSTT._language_codes("te") == ["te-IN", "en-IN"]


def test_arabic_wrong_script_is_rejected_for_ui_languages():
    assert _has_unexpected_arabic_script("نابل سیر مرسلین اپکس آجننجلی") is True
    assert _has_unexpected_arabic_script("నేను Hyderabad లో electrician పని చేస్తున్నాను") is False


def test_online_stt_uses_single_call_dedicated_transcriber():
    session = FakeSession()
    stt = OnlineSTT(api_key="secret", fallback_model="gemini-flash-latest", session=session)
    text, engine = stt.transcribe(b"RIFFfakewav", language="hi")
    assert "electrician" in text
    assert engine == "gemini-3.5-transcribe-inline"
    interaction = [x for x in session.posts if x[0].endswith("/v1beta/interactions")][0]
    config = interaction[1]["json"]["generation_config"]["transcription_config"]
    assert config["language_codes"] == ["hi-IN", "en-IN"]
    assert "electrician" in config["custom_vocabulary"]
    assert not session.deleted  # inline audio avoids upload/delete round trips


def test_frontend_routes_online_indic_audio_to_backend_not_browser_first():
    js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "if(selectedLanguage()!=='en')" in js
    assert "online-local-first" in js
    assert "postRecording('/stt/online')" in js
    assert "postRecording('/stt/offline')" in js


def test_online_stt_api_route_exists():
    app = (ROOT / "backend" / "api" / "app.py").read_text(encoding="utf-8")
    assert '@app.post("/stt/online"' in app
    assert "OnlineSTT(api_key=_ONLINE_EXTRACTOR.api_key" in app
