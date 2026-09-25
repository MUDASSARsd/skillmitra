import unittest
from backend.mapping import NQRCandidateRetriever, profile_signals
from backend.models.beneficiary import BeneficiaryProfile, Experience

class TestNQRMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.r=NQRCandidateRetriever()

    def test_no_signal_no_candidates(self):
        self.assertEqual(self.r.retrieve(BeneficiaryProfile()), [])

    def test_profile_signals_do_not_use_education_as_trade(self):
        p=BeneficiaryProfile(education={"level":"10th"}, interests=["electrical"])
        self.assertEqual([x[0] for x in profile_signals(p)], ["interest"])

    def test_electrical_retrieval(self):
        p=BeneficiaryProfile(skills=["electrical wiring"], interests=["electrician"])
        r=self.r.retrieve(p,10)
        blob=" ".join((x.qualification.title+" "+(x.qualification.proposed_occupation or "")) for x in r).lower()
        self.assertTrue("electric" in blob or "wiring" in blob)

    def test_plumbing_retrieval(self):
        p=BeneficiaryProfile(skills=["pipe fitting"], interests=["plumbing"])
        r=self.r.retrieve(p,10)
        blob=" ".join(x.qualification.title for x in r).lower()
        self.assertIn("plumb", blob)

    def test_computer_hardware_retrieval(self):
        p=BeneficiaryProfile(interests=["computer hardware"])
        r=self.r.retrieve(p,10)
        blob=" ".join(x.qualification.title for x in r).lower()
        self.assertTrue("computer" in blob or "hardware" in blob)

    def test_experience_is_a_signal(self):
        p=BeneficiaryProfile(experience=[Experience(domain="welding", duration_months=12)])
        self.assertTrue(any(s[0]=="experience" for s in profile_signals(p)))

    def test_offline_source_and_real_nqr_rows(self):
        p=BeneficiaryProfile(interests=["electrician"])
        r=self.r.retrieve(p,5)
        self.assertTrue(r)
        self.assertTrue(all(x.source=="local_nqr_fts5" for x in r))
        self.assertTrue(all(x.qualification.id is not None for x in r))

    def test_limit(self):
        p=BeneficiaryProfile(interests=["electrical"])
        self.assertLessEqual(len(self.r.retrieve(p,3)),3)

    def test_scores_bounded_and_sorted(self):
        p=BeneficiaryProfile(interests=["plumbing"], skills=["pipe fitting"])
        r=self.r.retrieve(p,10)
        scores=[x.retrieval_score for x in r]
        self.assertTrue(all(0 <= x <= 1 for x in scores))
        self.assertEqual(scores, sorted(scores, reverse=True))

if __name__=='__main__': unittest.main()
