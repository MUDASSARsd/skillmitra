import unittest
from backend.models.beneficiary import BeneficiaryProfile, Education, Experience, Location
from backend.nlu.base import ProfileExtractor
from backend.conversation import ProfileCompletenessChecker, CounterQuestionEngine, ConversationManager


class FakeExtractor(ProfileExtractor):
    def extract(self, text, current_profile=None, language_code=None):
        p = current_profile or BeneficiaryProfile()
        if "10th" in text:
            p.merge({"education": {"level": "10th", "status": "passed"}})
        if "electric" in text.lower():
            p.merge({"interests": ["electrical"]})
        return p


class TestConversationPhase4(unittest.TestCase):
    def setUp(self):
        self.checker = ProfileCompletenessChecker()
        self.engine = CounterQuestionEngine(self.checker)

    def test_empty_profile_not_ready(self):
        r = self.checker.check(BeneficiaryProfile())
        self.assertFalse(r.ready_for_mapping)
        self.assertEqual(r.missing_critical, [
            "education", "livelihood_signal", "experience",
            "employment_preference", "location", "training_willingness"
        ])

    def test_mapping_ready_with_education_and_interest(self):
        p = BeneficiaryProfile(education=Education(level="10th"), interests=["electrical"])
        self.assertFalse(self.checker.check(p).ready_for_mapping)

    def test_skill_is_valid_livelihood_signal(self):
        p = BeneficiaryProfile(education=Education(level="8th"), skills=["pipe fitting"])
        self.assertFalse(self.checker.check(p).ready_for_mapping)

    def test_occupation_is_valid_livelihood_signal(self):
        p = BeneficiaryProfile(education=Education(level="12th"), occupation="helper")
        self.assertFalse(self.checker.check(p).ready_for_mapping)

    def test_first_question_is_education(self):
        self.assertEqual(self.engine.next_missing_field(BeneficiaryProfile()), "education")

    def test_does_not_reask_known_education(self):
        p = BeneficiaryProfile(education=Education(level="10th"))
        self.assertEqual(self.engine.next_missing_field(p), "livelihood_signal")

    def test_experience_question_after_critical_fields(self):
        p = BeneficiaryProfile(education=Education(level="10th"), interests=["electrical"])
        self.assertEqual(self.engine.next_missing_field(p), "experience")

    def test_known_experience_not_reasked(self):
        p = BeneficiaryProfile(education=Education(level="10th"), interests=["electrical"],
                               experience=[Experience(domain="electrical", duration_months=12)])
        self.assertEqual(self.engine.next_missing_field(p), "employment_preference")

    def test_hindi_question(self):
        q = self.engine.next_question(BeneficiaryProfile(), "hi-IN")
        self.assertIn("योग्यता", q)
        self.assertIn("आपने", q)

    def test_telugu_question(self):
        q = self.engine.next_question(BeneficiaryProfile(), "te-IN")
        self.assertIn("అర్హత", q)

    def test_english_fallback(self):
        q = self.engine.next_question(BeneficiaryProfile(), "fr-FR")
        self.assertTrue(q.startswith("What is"))

    def test_no_question_when_enrichment_complete(self):
        p = BeneficiaryProfile(
            education=Education(level="10th"), interests=["electrical"],
            experience=[Experience(domain="electrical", duration_months=12)],
            employment_preference="job", location=Location(district="Hyderabad"),
            training_willingness=True,
        )
        self.assertIsNone(self.engine.next_question(p))

    def test_manager_preserves_multiturn_profile(self):
        manager = ConversationManager(FakeExtractor())
        t1 = manager.process("I like electrical work")
        self.assertEqual(t1.profile.interests, ["electrical"])
        self.assertEqual(t1.next_question, "What is the highest class or qualification you completed?")
        t2 = manager.process("10th pass", t1.profile)
        self.assertEqual(t2.profile.interests, ["electrical"])
        self.assertEqual(t2.profile.education.level, "10th")
        self.assertEqual(t2.next_question, "Do you have any work experience? If yes, what work did you do and for how long?")


if __name__ == "__main__":
    unittest.main()
