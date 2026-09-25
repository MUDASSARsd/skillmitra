"""
Unit Tests for Phase 3: Online Profile Extractor (Mocked LLM API Tests).
"""
import unittest
import json
from backend.models.beneficiary import BeneficiaryProfile, Education, Experience, Location
from backend.nlu.online_extractor import OnlineProfileExtractor


class TestOnlineProfileExtractorMocked(unittest.TestCase):

    def setUp(self):
        self.extractor = OnlineProfileExtractor(provider="gemini", api_key="mock_key")

    def test_1_english_unstructured_extraction(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": "10th", "status": "passed", "stream": None},
                "occupation": None,
                "skills": ["electrical wiring"],
                "interests": ["electrical"],
                "experience": [{"domain": "electrical", "duration_months": 24}],
                "location": {"state": None, "district": "Hyderabad"},
                "employment_preference": "job",
                "training_willingness": True,
                "mobility_km": None,
                "language": "en"
            })
        
        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("I passed 10th and worked in electrical wiring for 2 years in Hyderabad. Want a job.")
        self.assertEqual(profile.education.level, "10th")
        self.assertIn("electrical wiring", profile.skills)
        self.assertEqual(profile.experience[0].duration_months, 24)
        self.assertEqual(profile.location.district, "Hyderabad")

    def test_2_hindi_hinglish_extraction(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": "10th", "status": "passed", "stream": None},
                "occupation": None,
                "skills": ["electrical wiring"],
                "interests": ["electrical"],
                "experience": [{"domain": "electrical", "duration_months": 24}],
                "location": {"state": None, "district": "Hyderabad"},
                "employment_preference": "job",
                "training_willingness": True,
                "mobility_km": None,
                "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("Maine 10th complete kiya hai. 2 saal electrical wiring ka kaam kiya. Hyderabad mein job chahiye.")
        self.assertEqual(profile.education.level, "10th")
        self.assertEqual(profile.experience[0].duration_months, 24)

    def test_3_partial_answer(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": None, "status": None, "stream": None},
                "occupation": None,
                "skills": [],
                "interests": ["electrical"],
                "experience": [],
                "location": {"state": None, "district": None},
                "employment_preference": None,
                "training_willingness": None,
                "mobility_km": None,
                "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("Mujhe electrician banna hai.")
        self.assertEqual(profile.interests, ["electrical"])
        self.assertIsNone(profile.education.level)

    def test_4_education_extraction(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": "12th", "status": "passed", "stream": "Science"},
                "occupation": None, "skills": [], "interests": [], "experience": [],
                "location": {"state": None, "district": None}, "employment_preference": None,
                "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("I completed 12th in Science stream.")
        self.assertEqual(profile.education.level, "12th")
        self.assertEqual(profile.education.stream, "Science")

    def test_5_experience_years_to_months(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": None, "status": None, "stream": None},
                "occupation": None, "skills": [], "interests": [],
                "experience": [{"domain": "plumbing", "duration_months": 36}],
                "location": {"state": None, "district": None}, "employment_preference": None,
                "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("I did plumbing work for 3 years.")
        self.assertEqual(profile.experience[0].duration_months, 36)

    def test_6_experience_months(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": None, "status": None, "stream": None},
                "occupation": None, "skills": [], "interests": [],
                "experience": [{"domain": "shop helper", "duration_months": 8}],
                "location": {"state": None, "district": None}, "employment_preference": None,
                "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("8 months at mama shop.")
        self.assertEqual(profile.experience[0].duration_months, 8)

    def test_7_skill_extraction(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": None, "status": None, "stream": None},
                "occupation": None, "skills": ["soldering", "PCB assembly"], "interests": [],
                "experience": [], "location": {"state": None, "district": None},
                "employment_preference": None, "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("I know soldering and PCB assembly.")
        self.assertEqual(profile.skills, ["soldering", "PCB assembly"])

    def test_8_interest_extraction(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": None, "status": None, "stream": None},
                "occupation": None, "skills": [], "interests": ["solar panel installation"],
                "experience": [], "location": {"state": None, "district": None},
                "employment_preference": None, "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("I am interested in solar panel installation course.")
        self.assertEqual(profile.interests, ["solar panel installation"])

    def test_9_location_extraction(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": None, "status": None, "stream": None},
                "occupation": None, "skills": [], "interests": [], "experience": [],
                "location": {"state": None, "district": "Warangal"},
                "employment_preference": None, "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("Warangal mein rehta hoon.")
        self.assertEqual(profile.location.district, "Warangal")
        self.assertIsNone(profile.location.state)

    def test_10_employment_preference(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": None, "status": None, "stream": None},
                "occupation": None, "skills": [], "interests": [], "experience": [],
                "location": {"state": None, "district": None},
                "employment_preference": "self_employment",
                "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("Mujhe khud ka business chalu karna hai.")
        self.assertEqual(profile.employment_preference, "self_employment")

    def test_11_missing_information_remains_null(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": "8th", "status": "passed", "stream": None},
                "occupation": None, "skills": [], "interests": [], "experience": [],
                "location": {"state": None, "district": None},
                "employment_preference": None, "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("Maine 8th pass kiya.")
        self.assertEqual(profile.education.level, "8th")
        self.assertIsNone(profile.location.district)
        self.assertEqual(profile.experience, [])

    def test_12_multi_turn_profile_preservation(self):
        current = BeneficiaryProfile(
            interests=["electrical"]
        )
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": "10th", "status": "passed", "stream": None},
                "occupation": None, "skills": [], "interests": [], "experience": [],
                "location": {"state": None, "district": None},
                "employment_preference": None, "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        updated = extractor.extract("10th pass", current_profile=current)
        self.assertEqual(updated.interests, ["electrical"])
        self.assertEqual(updated.education.level, "10th")

    def test_13_existing_values_are_not_erased(self):
        current = BeneficiaryProfile(
            education=Education(level="10th", status="passed"),
            interests=["electrical"]
        )
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": None, "status": None, "stream": None},
                "occupation": None, "skills": [], "interests": [],
                "experience": [{"domain": "electrical", "duration_months": 8}],
                "location": {"state": None, "district": None},
                "employment_preference": None, "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        updated = extractor.extract("8 months electrical experience", current_profile=current)
        self.assertEqual(updated.education.level, "10th")
        self.assertEqual(updated.interests, ["electrical"])
        self.assertEqual(updated.experience[0].duration_months, 8)

    def test_14_invalid_llm_json(self):
        def mock_caller(prompt, text):
            return "This is not JSON text at all!"

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        with self.assertRaises(ValueError):
            extractor.extract("Hello")

    def test_15_api_failure(self):
        def mock_caller(prompt, text):
            raise RuntimeError("API Connection Timeout")

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        with self.assertRaises(RuntimeError):
            extractor.extract("Hello")

    def test_16_extra_unexpected_llm_fields(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": "10th", "status": "passed", "stream": None},
                "extra_field_from_llm": "should be ignored by pydantic or tolerated",
                "occupation": None, "skills": [], "interests": [], "experience": [],
                "location": {"state": None, "district": None},
                "employment_preference": None, "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("10th pass")
        self.assertEqual(profile.education.level, "10th")

    def test_17_no_experience_explicitly_stated(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": "12th", "status": "passed", "stream": None},
                "occupation": None, "skills": [], "interests": [],
                "experience": [],
                "location": {"state": None, "district": None},
                "employment_preference": None, "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("I studied 12th but I have no work experience.")
        self.assertEqual(profile.experience, [])

    def test_18_experience_domain_known_but_duration_unknown(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": None, "status": None, "stream": None},
                "occupation": None, "skills": [], "interests": [],
                "experience": [{"domain": "electrical wiring", "duration_months": None}],
                "location": {"state": None, "district": None},
                "employment_preference": None, "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("I know electrical wiring work.")
        self.assertEqual(profile.experience[0].domain, "electrical wiring")
        self.assertIsNone(profile.experience[0].duration_months)

    def test_19_duration_known_but_domain_unknown(self):
        def mock_caller(prompt, text):
            return json.dumps({
                "education": {"level": None, "status": None, "stream": None},
                "occupation": None, "skills": [], "interests": [],
                "experience": [{"domain": None, "duration_months": 24}],
                "location": {"state": None, "district": None},
                "employment_preference": None, "training_willingness": None, "mobility_km": None, "language": None
            })

        extractor = OnlineProfileExtractor(api_caller=mock_caller)
        profile = extractor.extract("I have worked for 2 years.")
        self.assertIsNone(profile.experience[0].domain)
        self.assertEqual(profile.experience[0].duration_months, 24)


if __name__ == "__main__":
    unittest.main()


def test_online_short_training_answer_gets_question_context():
    from backend.models.beneficiary import BeneficiaryProfile, Education, Location, Experience
    captured = {}
    def caller(prompt, text):
        captured["prompt"] = prompt
        captured["text"] = text
        return json.dumps({
            "education":{"level":None,"status":None,"stream":None},
            "occupation":None,"skills":[],"interests":[],"experience":[],
            "location":{"state":None,"district":None},
            "employment_preference":None,"training_willingness":True,
            "mobility_km":None,"language":None
        })
    current=BeneficiaryProfile(
        education=Education(level="10th",status="passed"), occupation="electrician", skills=["electrical"],
        experience=[Experience(domain="electrical",duration_months=12)], location=Location(district="Hyderabad"),
        employment_preference="job"
    )
    ex=OnlineProfileExtractor(api_caller=caller)
    out=ex.extract("हाँ ज़रूर करूँगा", current_profile=current, language_code="hi-IN")
    assert "CURRENT_QUESTION_TOPIC: training_willingness" in captured["prompt"]
    assert out.training_willingness is True
