import os, unittest
from backend.eligibility_engine import EligibilityEngine
from backend.models.beneficiary import BeneficiaryProfile, Education, Experience
from backend.models.eligibility import EligibilityStatus
DB=os.path.join(os.path.dirname(__file__), '..','data','nqr_database.db')
class TestEligibilityEngine(unittest.TestCase):
 def setUp(self): self.e=EligibilityEngine(DB)
 def p(self, level=None, stream=None, months=None):
  return BeneficiaryProfile(education=Education(level=level,status='passed' if level else None,stream=stream),experience=[] if months is None else [Experience(domain='oil and gas',duration_months=months)])
 def test_missing_routes(self): self.assertEqual(self.e.evaluate(self.p('10th'),'DOES-NOT-EXIST').status,EligibilityStatus.ELIGIBILITY_DATA_MISSING)
 def test_route_1284_8th_one_year(self):
  x=self.e.evaluate(self.p('8th',months=12),'2020/HYC/HSSCI/3770'); self.assertEqual(x.status,EligibilityStatus.ELIGIBLE); self.assertEqual(x.matched_route.route_number,1)
 def test_higher_grade_satisfies_lower_route(self): self.assertEqual(self.e.evaluate(self.p('10th',months=12),'2020/HYC/HSSCI/3770').status,EligibilityStatus.ELIGIBLE)
 def test_9th_no_experience_route(self): self.assertEqual(self.e.evaluate(self.p('9th'),'2020/HYC/HSSCI/3770').status,EligibilityStatus.ELIGIBLE)
 def test_missing_experience_is_not_zero(self): self.assertEqual(self.e.evaluate(self.p('8th'),'2020/HYC/HSSCI/3770').status,EligibilityStatus.NEEDS_MORE_INFORMATION)
 def test_too_low_but_other_route_possible_missing(self): self.assertEqual(self.e.evaluate(self.p('5th'),'2020/HYC/HSSCI/3770').status,EligibilityStatus.NEEDS_MORE_INFORMATION)
 def test_10th_24_months_route5(self):
  x=self.e.evaluate(self.p('10th',months=24),'2020/HYC/HSSCI/3769'); self.assertEqual(x.status,EligibilityStatus.ELIGIBLE); self.assertEqual(x.matched_route.route_number,5)
 def test_10th_without_experience_needs_info(self): self.assertEqual(self.e.evaluate(self.p('10th'),'2020/HYC/HSSCI/3769').status,EligibilityStatus.NEEDS_MORE_INFORMATION)
 def test_12th_science_no_exp(self):
  x=self.e.evaluate(self.p('12th','Science'),'2020/HYC/HSSCI/3769'); self.assertEqual(x.status,EligibilityStatus.ELIGIBLE); self.assertEqual(x.matched_route.route_number,3)
 def test_12th_unknown_stream_needs_info(self): self.assertEqual(self.e.evaluate(self.p('12th'),'2020/HYC/HSSCI/3769').status,EligibilityStatus.NEEDS_MORE_INFORMATION)
 def test_wrong_stream_can_fall_to_exp_route_if_missing(self): self.assertEqual(self.e.evaluate(self.p('12th','Arts'),'2020/HYC/HSSCI/3769').status,EligibilityStatus.NEEDS_MORE_INFORMATION)
 def test_wrong_stream_with_24m_uses_route5(self): self.assertEqual(self.e.evaluate(self.p('12th','Arts',24),'2020/HYC/HSSCI/3769').status,EligibilityStatus.ELIGIBLE)
if __name__=='__main__': unittest.main()
