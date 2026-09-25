import unittest
from fastapi.testclient import TestClient
from backend.api.app import app


class TestOfflineConversationAPI(unittest.TestCase):
    def setUp(self):
        self.c = TestClient(app)

    def test_offline_conversation(self):
        r = self.c.post(
            '/conversation/offline',
            json={
                'text': '10th pass, 2 saal electrical wiring ka kaam kiya, job chahiye',
                'language_code': 'hinglish',
                'include_recommendations': True,
            }
        )
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertTrue(d['extraction_mode'].startswith('offline_'))
        self.assertEqual(d['profile']['education']['level'], '10th')
        if d['profile']['experience']:
            self.assertEqual(d['profile']['experience'][0]['duration_months'], 24)

    def test_offline_multiturn(self):
        r1 = self.c.post(
            '/conversation/offline',
            json={'text': 'Mujhe electrician banna hai', 'language_code': 'hinglish'}
        ).json()
        r2 = self.c.post(
            '/conversation/offline',
            json={'text': '10th pass hoon', 'current_profile': r1['profile'], 'language_code': 'hinglish'}
        ).json()
        if r2['profile']['education']['level']:
            self.assertIn(r2['profile']['education']['level'], ('10th', '10'))
        # Ensure initial livelihood interest/skill was preserved across turns
        combined = (r2['profile']['interests'] + r2['profile']['skills'] + [r2['profile']['occupation'] or ''])
        self.assertTrue(any('electric' in str(x).lower() for x in combined))


if __name__ == '__main__':
    unittest.main()
