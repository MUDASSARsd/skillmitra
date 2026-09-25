import unittest
from fastapi.testclient import TestClient
from backend.api.app import app

class TestVoiceFrontend(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_voice_controls_render(self):
        html = self.client.get('/app').text
        self.assertIn('id="micBtn"', html)
        self.assertIn('id="speakToggle"', html)
        self.assertIn('id="voiceStatus"', html)

    def test_voice_input_has_browser_fallback(self):
        js = self.client.get('/ui/app.js').text
        self.assertIn('window.SpeechRecognition || window.webkitSpeechRecognition', js)
        self.assertIn('Speech recognition is not supported by this browser', js)

    def test_tts_language_and_cancel(self):
        js = self.client.get('/ui/app.js').text
        self.assertIn("return 'hi-IN'", js)
        self.assertIn("return 'en-IN'", js)
        self.assertIn("return 'te-IN'", js)
        self.assertIn('window.speechSynthesis.cancel()', js)

if __name__ == '__main__':
    unittest.main()
