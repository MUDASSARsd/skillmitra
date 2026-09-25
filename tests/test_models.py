"""
Unit Tests for Phase 2: Common BeneficiaryProfile & Domain Schemas.
"""
import unittest
import json
import sqlite3
from pathlib import Path
from backend.models.beneficiary import BeneficiaryProfile, Education, Experience, Location
from backend.models.qualification import Qualification
from backend.models.eligibility import EligibilityRoute, EligibilityStatus
from backend.models.recommendation import RecommendationResult

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "nqr_database.db"


class TestDomainModels(unittest.TestCase):

    def test_1_empty_beneficiary_profile(self):
        profile = BeneficiaryProfile()
        self.assertIsNone(profile.education.level)
        self.assertIsNone(profile.education.status)
        self.assertIsNone(profile.education.stream)
        self.assertIsNone(profile.occupation)
        self.assertEqual(profile.skills, [])
        self.assertEqual(profile.interests, [])
        self.assertEqual(profile.experience, [])
        self.assertIsNone(profile.location.state)
        self.assertIsNone(profile.location.district)
        self.assertIsNone(profile.employment_preference)
        self.assertIsNone(profile.training_willingness)
        self.assertIsNone(profile.mobility_km)
        self.assertIsNone(profile.language)

    def test_2_partially_completed_profile(self):
        profile = BeneficiaryProfile(
            education=Education(level="10th", status="passed"),
            interests=["electrical"]
        )
        self.assertEqual(profile.education.level, "10th")
        self.assertEqual(profile.interests, ["electrical"])
        self.assertIsNone(profile.location.state)
        self.assertEqual(profile.experience, [])

    def test_3_fully_completed_profile(self):
        profile = BeneficiaryProfile(
            education=Education(level="10th", status="passed", stream=None),
            occupation="Electrician Assistant",
            skills=["electrical wiring", "circuit testing"],
            interests=["electrical", "solar energy"],
            experience=[Experience(domain="electrical", duration_months=24)],
            location=Location(state="Telangana", district="Hyderabad"),
            employment_preference="job",
            training_willingness=True,
            mobility_km=25,
            language="hi-IN"
        )
        self.assertEqual(profile.education.level, "10th")
        self.assertEqual(profile.location.district, "Hyderabad")
        self.assertTrue(profile.training_willingness)
        self.assertEqual(profile.experience[0].duration_months, 24)

    def test_4_multiple_experience_records(self):
        profile = BeneficiaryProfile(
            experience=[
                Experience(domain="electrical wiring", duration_months=24),
                Experience(domain="appliance repair", duration_months=12)
            ]
        )
        self.assertEqual(len(profile.experience), 2)
        self.assertEqual(profile.experience[0].domain, "electrical wiring")
        self.assertEqual(profile.experience[0].duration_months, 24)
        self.assertEqual(profile.experience[1].domain, "appliance repair")
        self.assertEqual(profile.experience[1].duration_months, 12)

    def test_5_missing_education(self):
        profile = BeneficiaryProfile(
            interests=["plumbing"],
            experience=[Experience(domain="plumbing", duration_months=6)]
        )
        self.assertIsNone(profile.education.level)
        self.assertIsNone(profile.education.status)
        self.assertEqual(profile.interests, ["plumbing"])

    def test_6_missing_experience(self):
        profile = BeneficiaryProfile(
            education=Education(level="12th", status="passed"),
            skills=["computer basics"]
        )
        self.assertEqual(profile.experience, [])

    def test_7_multiple_eligibility_routes(self):
        route1 = EligibilityRoute(
            code="2020/HYC/HSSCI/3770",
            route_number=1,
            criteria_1="8th",
            criteria_2="Passed",
            experience="1 year",
            experience_months=12
        )
        route2 = EligibilityRoute(
            code="2020/HYC/HSSCI/3770",
            route_number=2,
            criteria_1="5th",
            criteria_2="Passed",
            experience="4 years",
            experience_months=48
        )
        self.assertNotEqual(route1.criteria_1, route2.criteria_1)
        self.assertNotEqual(route1.experience_months, route2.experience_months)
        self.assertEqual(route1.route_number, 1)
        self.assertEqual(route2.route_number, 2)

    def test_8_eligibility_data_missing_status(self):
        qual = Qualification(
            s_no=1,
            title="Solar PV Installer",
            code="2023/SOL/001"
        )
        result = RecommendationResult(
            qualification=qual,
            eligibility_status=EligibilityStatus.ELIGIBILITY_DATA_MISSING,
            warnings=["Eligibility route data is unavailable in current local database."]
        )
        self.assertEqual(result.eligibility_status, EligibilityStatus.ELIGIBILITY_DATA_MISSING)
        self.assertEqual(len(result.warnings), 1)

    def test_9_serialization_to_json(self):
        profile = BeneficiaryProfile(
            education=Education(level="10th", status="passed"),
            interests=["electrical"],
            location=Location(state="Telangana", district="Hyderabad")
        )
        json_str = profile.model_dump_json(indent=2)
        dict_val = json.loads(json_str)
        self.assertEqual(dict_val["education"]["level"], "10th")
        self.assertEqual(dict_val["location"]["district"], "Hyderabad")

        # Roundtrip deserialization
        restored = BeneficiaryProfile.model_validate_json(json_str)
        self.assertEqual(restored.education.level, "10th")
        self.assertEqual(restored.location.district, "Hyderabad")

    def test_10_loading_qualification_from_phase1_db(self):
        self.assertTrue(DB_PATH.exists(), f"Phase 1 SQLite database must exist at: {DB_PATH}")
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM qualifications WHERE code = '2020/HYC/HSSCI/3770'")
        qual_row = cursor.fetchone()
        self.assertIsNotNone(qual_row, "Qualification row should exist in Phase 1 DB")

        qual_model = Qualification.from_sqlite_row(qual_row)
        self.assertEqual(qual_model.code, "2020/HYC/HSSCI/3770")
        self.assertEqual(qual_model.title, "Line Patrolling Man (Oil  Gas)")

        cursor.execute("SELECT * FROM eligibility_routes WHERE code = '2020/HYC/HSSCI/3770' ORDER BY route_number")
        route_rows = cursor.fetchall()
        self.assertEqual(len(route_rows), 4, "Line Patrolling Man should have 4 routes in Phase 1 DB")

        route_models = [EligibilityRoute.model_validate(dict(r)) for r in route_rows]
        self.assertEqual(route_models[0].criteria_1, "8th")
        self.assertEqual(route_models[0].experience_months, 12)
        conn.close()

    def test_multi_turn_profile_merge(self):
        # Turn 1
        p = BeneficiaryProfile()
        p.merge({"interests": ["electrical"], "education": {"level": "10th"}})
        self.assertEqual(p.interests, ["electrical"])
        self.assertEqual(p.education.level, "10th")

        # Turn 2: User adds experience in electrical
        p.merge({"experience": [{"domain": "electrical", "duration_months": 8}]})
        # Verify Turn 1 values are preserved!
        self.assertEqual(p.interests, ["electrical"])
        self.assertEqual(p.education.level, "10th")
        self.assertEqual(len(p.experience), 1)
        self.assertEqual(p.experience[0].duration_months, 8)


if __name__ == "__main__":
    unittest.main()
