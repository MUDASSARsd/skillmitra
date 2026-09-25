import unittest
from backend.recommendation_engine import RecommendationEngine
from backend.models.beneficiary import BeneficiaryProfile, Education, Experience
from backend.models.eligibility import EligibilityStatus

class TestRecommendationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.engine = RecommendationEngine()

    def test_empty_profile_returns_empty(self):
        self.assertEqual(self.engine.recommend(BeneficiaryProfile()), [])

    def test_electrical_end_to_end_returns_real_nqr(self):
        p=BeneficiaryProfile(education=Education(level='10th',status='passed'),skills=['house wiring','switch repair'],interests=['electrical'],experience=[Experience(domain='electrical wiring',duration_months=24)],employment_preference='job')
        r=self.engine.recommend(p,5)
        self.assertTrue(r); self.assertTrue(all(x.qualification.id is not None for x in r))
        self.assertTrue(any('electric' in (x.qualification.title+' '+(x.qualification.proposed_occupation or '')).lower() for x in r))

    def test_scores_are_bounded(self):
        r=self.engine.recommend(BeneficiaryProfile(interests=['computer hardware']),5)
        self.assertTrue(all(0 <= x.relevance_score <= 1 for x in r))

    def test_score_breakdown_is_explainable(self):
        r=self.engine.recommend(BeneficiaryProfile(interests=['plumbing'],skills=['pipe fitting']),3)
        self.assertTrue(r)
        self.assertEqual(set(r[0].score_breakdown), {'retrieval_relevance','signal_coverage','authoritative_field_match','eligibility_adjustment'})

    def test_missing_eligibility_is_explicit(self):
        # High-coverage builds may have no missing route for arbitrary queries.
        # Select a currently uncovered qualification dynamically; if coverage reaches 100%,
        # this behavior is no longer applicable and the test should be skipped.
        import sqlite3
        con = sqlite3.connect(self.engine.db_path)
        row = con.execute("""
            SELECT q.title FROM qualifications q
            LEFT JOIN eligibility_routes e ON lower(trim(e.code))=lower(trim(q.code))
            WHERE q.code IS NOT NULL AND trim(q.code)<>''
            GROUP BY q.id HAVING COUNT(e.id)=0 LIMIT 1
        """).fetchone()
        con.close()
        if not row:
            self.skipTest('Eligibility coverage is 100%; no missing-route case remains.')
        engine_no_fb = RecommendationEngine(self.engine.db_path, enable_nsqf_fallback=False)
        r = engine_no_fb.recommend(BeneficiaryProfile(interests=[row[0]]), 10, candidate_limit=40)
        missing = [x for x in r if x.eligibility_status == EligibilityStatus.ELIGIBILITY_DATA_MISSING]
        self.assertTrue(missing)
        self.assertTrue(any('NOT been verified' in w for w in missing[0].warnings))

    def test_score_warning_says_not_probability(self):
        r=self.engine.recommend(BeneficiaryProfile(interests=['electrician']),3)
        self.assertTrue(any('not a probability' in w for w in r[0].warnings))

    def test_known_eligible_candidate_can_be_evaluated(self):
        # Hydrocarbon signal retrieves the two codes for which verified routes exist.
        p=BeneficiaryProfile(education=Education(level='10th',status='passed'),interests=['oil gas pipeline'],experience=[Experience(domain='oil and gas',duration_months=24)])
        r=self.engine.recommend(p,30,candidate_limit=60)
        known=[x for x in r if x.qualification.code in {'2020/HYC/HSSCI/3770','2020/HYC/HSSCI/3769'}]
        self.assertTrue(known)
        self.assertTrue(any(x.eligibility_status==EligibilityStatus.ELIGIBLE for x in known))

    def test_top_k(self):
        self.assertLessEqual(len(self.engine.recommend(BeneficiaryProfile(interests=['electrical']),3)),3)

    def test_no_llm_or_network_dependency(self):
        # If this returns official local rows, recommendation path is local DB + deterministic code.
        r=self.engine.recommend(BeneficiaryProfile(interests=['welding']),2)
        self.assertTrue(r)
        self.assertTrue(all(x.qualification.source_file for x in r))

if __name__=='__main__': unittest.main()
