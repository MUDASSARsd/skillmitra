import unittest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.models.beneficiary import BeneficiaryProfile
from backend.recommendation_engine import RecommendationEngine


class TestV26AdversarialSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.engine = RecommendationEngine()

    def test_generic_electrician_does_not_surface_pwd_specific_qualification(self):
        p = BeneficiaryProfile(
            education={"level": "10th", "status": "completed"},
            occupation="electrician",
            skills=["wiring", "electrical safety"],
            location={"state": "Telangana", "district": "Hyderabad"},
        )
        recs = self.engine.recommend(p, top_k=10, candidate_limit=60)
        self.assertGreater(len(recs), 0)
        for rec in recs:
            hay = f"{rec.qualification.code or ''} {rec.qualification.title or ''}".casefold()
            self.assertNotIn("scpwd", hay)
            self.assertNotIn("divyangjan", hay)
            self.assertNotIn("-pwd", hay)
            self.assertNotIn("/pwd/", hay)

    def test_tailor_does_not_surface_pwd_variants_when_status_unknown(self):
        p = BeneficiaryProfile(occupation="tailor", skills=["sewing"])
        recs = self.engine.recommend(p, top_k=10, candidate_limit=60)
        self.assertTrue(recs)
        self.assertFalse(any("pwd" in f"{r.qualification.code} {r.qualification.title}".casefold() for r in recs))

    def test_explicit_pwd_context_can_surface_pwd_qualification(self):
        p = BeneficiaryProfile(
            occupation="tailor",
            skills=["sewing"],
            disability_category="PwD",
        )
        recs = self.engine.recommend(p, top_k=10, candidate_limit=60)
        self.assertTrue(any("pwd" in f"{r.qualification.code} {r.qualification.title}".casefold() or "divyangjan" in r.qualification.title.casefold() for r in recs))

    def test_minimal_profile_fails_safe_with_zero_recommendations(self):
        res = self.client.post("/recommend/with-opportunities", json={"profile": {}})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["count"], 0)
        self.assertEqual(body["results"], [])

    def test_unknown_location_does_not_claim_local_job_scope(self):
        res = self.client.post(
            "/recommend/with-opportunities",
            json={"profile": {"occupation": "solar installer", "skills": ["wiring"]}, "top_k": 2},
        )
        self.assertEqual(res.status_code, 200)
        for item in res.json()["results"]:
            self.assertNotIn(item["job_location_scope"], {"district", "state"})

    def test_skill_gap_absence_is_not_asserted_as_lack(self):
        # An empty skill profile should produce evidence gaps, not fabricated competence claims.
        p = BeneficiaryProfile(occupation="electrician")
        recs = self.engine.recommend(p, top_k=1)
        self.assertTrue(recs)
        code = recs[0].qualification.code
        res = self.client.post("/skill-gap/analyze", json={"profile": p.model_dump(), "qualification_code": code})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        # Current model names this collection not_evidenced_skills / missing evidence; accept either stable representation.
        text = str(body).casefold()
        self.assertTrue("evidenc" in text or "unknown" in text)

    def test_live_batch_endpoint_does_not_invent_seats(self):
        res = self.client.get("/training/live-batches", params={"qualification_code": "HSS/Q4003", "state": "UTTAR PRADESH", "district": "BAREILLY"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        if body.get("count", 0):
            first = body["batches"][0]
            # Captured SIDH payload has BatchSize but no dedicated remaining-seat value.
            self.assertIn(first.get("seats_available"), (None, "unknown"))


if __name__ == "__main__":
    unittest.main()
