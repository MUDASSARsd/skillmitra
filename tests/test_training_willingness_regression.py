import unittest

from backend.models.beneficiary import BeneficiaryProfile, Education, Location, Experience
from backend.nlu.local_extractor import LocalProfileExtractor
from backend.conversation.completeness import ProfileCompletenessChecker


class TrainingWillingnessRegressionTests(unittest.TestCase):
    def setUp(self):
        self.extractor = LocalProfileExtractor()
        self.profile = BeneficiaryProfile(
            education=Education(level="10th"),
            occupation="electrician",
            skills=["electrical"],
            experience=[Experience(domain="electrical", duration_months=12)],
            location=Location(district="Hyderabad", state="Telangana"),
            employment_preference="job",
            training_willingness=None,
        )

    def check(self, text, expected):
        p = self.extractor.extract(text, self.profile.model_copy(deep=True), "en")
        self.assertIs(p.training_willingness, expected)
        self.assertTrue(ProfileCompletenessChecker().check(p).ready_for_mapping)

    def test_yeah_i_will_take_it(self):
        self.check("yeah I will take it", True)

    def test_yeah_i_will_take(self):
        self.check("yeah I will take", True)

    def test_sure_i_can_do_training(self):
        self.check("sure, I can do training", True)

    def test_natural_no(self):
        self.check("no, I do not want training", False)


if __name__ == "__main__":
    unittest.main()
