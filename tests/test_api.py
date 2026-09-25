import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.models.beneficiary import BeneficiaryProfile, Education

client = TestClient(app)

class TestAPI(unittest.TestCase):
    def test_root(self):
        r = client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_health(self):
        r = client.get("/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["database_ready"])
        self.assertGreater(body["qualification_count"], 2000)

    def test_offline_recommend(self):
        payload = {"profile": {
            "education": {"level": "10th", "status": "passed"},
            "skills": ["house wiring", "switch repair"],
            "interests": ["electrical"],
            "experience": [{"domain": "electrical wiring", "duration_months": 24}],
            "employment_preference": "job"
        }, "top_k": 3}
        r = client.post("/recommend", json=payload)
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertEqual(body["mode"], "offline_deterministic")
        self.assertEqual(body["count"], 3)
        self.assertTrue(any("electric" in x["qualification"]["title"].lower() for x in body["recommendations"]))

    def test_recommend_validation(self):
        r = client.post("/recommend", json={"profile": {}, "top_k": 0})
        self.assertEqual(r.status_code, 422)

    @patch("backend.api.app._conversation_manager")
    def test_conversation_not_ready(self, manager_factory):
        from backend.conversation.session import ConversationTurn
        from backend.conversation.completeness import CompletenessReport
        p = BeneficiaryProfile(interests=["electrical"])
        manager_factory.return_value.process.return_value = ConversationTurn(
            p, CompletenessReport(["education"], ["experience"]),
            "What is the highest class or qualification you completed?"
        )
        r = client.post("/conversation", json={"text": "Mujhe electrician banna hai."})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertFalse(body["ready_for_mapping"])
        self.assertEqual(body["recommendations"], [])
        self.assertIn("education", body["missing_critical"])

    @patch("backend.api.app._conversation_manager")
    def test_conversation_ready_runs_recommendation(self, manager_factory):
        from backend.conversation.session import ConversationTurn
        from backend.conversation.completeness import CompletenessReport
        p = BeneficiaryProfile(education=Education(level="10th", status="passed"), interests=["electrical"])
        manager_factory.return_value.process.return_value = ConversationTurn(
            p, CompletenessReport([], ["experience"]),
            "Do you have any work experience?"
        )
        r = client.post("/conversation", json={"text": "10th pass", "top_k": 2})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ready_for_mapping"])
        self.assertEqual(len(body["recommendations"]), 2)

if __name__ == "__main__": unittest.main()
