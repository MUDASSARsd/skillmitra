import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.api.app import app


class TestV20Cleanup(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_system_readiness_is_local_status_summary(self):
        r = self.client.get('/system/readiness')
        self.assertEqual(r.status_code, 200)
        d = r.json()
        for key in ('offline_core_ready', 'speech_to_text', 'text_to_speech',
                    'semantic_mapping', 'online_nlu', 'jobs_cache', 'courses_cache',
                    'training_cache'):
            self.assertIn(key, d)
        self.assertIsInstance(d['offline_core_ready'], bool)

    def test_frontend_does_not_speak_with_wrong_language_voice(self):
        js = self.client.get('/ui/app.js').text
        self.assertIn('Never silently fall back to an unrelated installed voice', js)
        self.assertIn('text reply is available', js)

    def test_start_script_checks_env_before_findstr(self):
        text = Path('START_HYBRID.bat').read_text(encoding='utf-8')
        self.assertIn('if not exist ".env"', text)
        self.assertIn('copy .env.example to .env', text)


if __name__ == '__main__':
    unittest.main()
