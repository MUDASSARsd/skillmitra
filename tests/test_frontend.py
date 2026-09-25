import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from backend.api.app import app

class TestFrontend(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_frontend_route(self):
        r = self.client.get('/app')
        self.assertEqual(r.status_code, 200)
        self.assertIn('SkillMitra', r.text)
        self.assertIn('Recommended pathways', r.text)

    def test_frontend_assets(self):
        css = self.client.get('/ui/styles.css')
        js = self.client.get('/ui/app.js')
        self.assertEqual(css.status_code, 200)
        self.assertEqual(js.status_code, 200)
        self.assertIn('offlineDemoBtn', js.text)
        self.assertIn('SpeechRecognition', js.text)
        self.assertIn('speechSynthesis', js.text)
        self.assertIn('micBtn', js.text)

    def test_root_advertises_frontend(self):
        r = self.client.get('/')
        self.assertEqual(r.json().get('frontend'), '/app')

if __name__ == '__main__':
    unittest.main()
