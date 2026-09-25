import json
import unittest
from backend.models.beneficiary import BeneficiaryProfile, Education, Experience, Location
from backend.nlu.ollama_extractor import (
    OllamaProfileExtractor, _focus_guard, _cross_field_sanity, _coerce_payload,
)
from backend.conversation.completeness import ProfileCompletenessChecker
from backend.conversation.questions import CounterQuestionEngine
from backend.recommendation_engine import RecommendationEngine


class FakeResponse:
    def __init__(self, body, ok=True, status_code=200):
        self._body = body
        self.ok = ok
        self.status_code = status_code
        self.text = json.dumps(body)
    def json(self):
        return self._body
    def raise_for_status(self):
        if not self.ok:
            raise RuntimeError(self.text)


class TestStabilityMatrix(unittest.TestCase):
    def test_focus_location_cannot_corrupt_other_fields(self):
        payload = _coerce_payload({
            'education': {'level': 'not-completed', 'status': None, 'stream': None},
            'occupation': 'housekeeping', 'skills': ['cleaning'], 'interests': ['Hyderabad'],
            'experience': [{'domain':'housekeeping','duration_months':1}],
            'location': {'state': None, 'district': 'Hyderabad'},
            'employment_preference': 'job', 'training_willingness': False,
            'mobility_km': None, 'language': 'te'
        })
        guarded = _focus_guard(payload, 'location')
        self.assertEqual(guarded['location']['district'], 'Hyderabad')
        self.assertIsNone(guarded['occupation'])
        self.assertEqual(guarded['skills'], [])
        self.assertEqual(guarded['interests'], [])
        self.assertEqual(guarded['experience'], [])
        self.assertIsNone(guarded['training_willingness'])

    def test_focus_training_cannot_corrupt_profile(self):
        payload = _coerce_payload({
            'education': {'level': '12th', 'status':'passed','stream':None},
            'occupation':'cleaner','skills':['cleaning'],'interests':['Hyderabad'],
            'experience':[{'domain':'cleaning','duration_months':1}],
            'location': {'state':None,'district':'Hyderabad'},
            'employment_preference':'job','training_willingness':True,
            'mobility_km':None,'language':'hi'
        })
        guarded = _focus_guard(payload, 'training_willingness')
        self.assertTrue(guarded['training_willingness'])
        self.assertIsNone(guarded['occupation'])
        self.assertEqual(guarded['skills'], [])
        self.assertIsNone(guarded['location']['district'])

    def test_location_is_removed_from_interest_leakage(self):
        payload = _coerce_payload({
            'education': {'level':None,'status':None,'stream':None},
            'occupation':None,'skills':[],'interests':['Hyderabad','electrical'],
            'experience':[], 'location':{'state':'Telangana','district':'Hyderabad'},
            'employment_preference':None,'training_willingness':None,
            'mobility_km':None,'language':'te'
        })
        cleaned = _cross_field_sanity(payload)
        self.assertEqual(cleaned['interests'], ['electrical'])

    def test_dropout_status_not_misused_as_education_level(self):
        payload = _coerce_payload({
            'education': {'level':'not-completed','status':None,'stream':None},
            'occupation':None,'skills':[],'interests':[],'experience':[],
            'location':{'state':None,'district':None},'employment_preference':None,
            'training_willingness':None,'mobility_km':None,'language':'te'
        })
        cleaned = _cross_field_sanity(payload)
        self.assertIsNone(cleaned['education']['level'])
        self.assertEqual(cleaned['education']['status'], 'dropout')

    def test_construction_profile_returns_nqr_matches(self):
        p = BeneficiaryProfile(
            education=Education(level='10th', status='passed'),
            occupation='construction worker', skills=['masonry'],
            experience=[Experience(domain='construction', duration_months=12)],
            employment_preference='job', language='te'
        )
        recs = RecommendationEngine().recommend(p, top_k=5)
        self.assertTrue(recs)
        titles = ' | '.join(r.qualification.title.lower() for r in recs)
        self.assertTrue(any(k in titles for k in ('mason','construction','brick','concrete')))

    def test_electrician_profile_returns_nqr_matches(self):
        p = BeneficiaryProfile(
            education=Education(level='10th', status='passed'),
            occupation='electrician', skills=['electrical wiring'],
            experience=[Experience(domain='electrical', duration_months=12)],
            employment_preference='job', language='en'
        )
        recs = RecommendationEngine().recommend(p, top_k=5)
        self.assertTrue(recs)

    def test_profile_ready_requires_education_and_livelihood(self):
        checker = ProfileCompletenessChecker()
        p = BeneficiaryProfile(education=Education(level='10th', status='passed'), occupation='electrician')
        self.assertFalse(checker.check(p).ready_for_mapping)
        p2 = BeneficiaryProfile(occupation='electrician')
        self.assertFalse(checker.check(p2).ready_for_mapping)

    def test_question_order_is_stable(self):
        q = CounterQuestionEngine()
        p = BeneficiaryProfile()
        self.assertEqual(q.next_missing_field(p), 'education')
        p.education = Education(level='10th', status='passed')
        self.assertEqual(q.next_missing_field(p), 'livelihood_signal')
        p.occupation = 'electrician'
        self.assertEqual(q.next_missing_field(p), 'experience')

    def test_quality_model_used_for_open_complex_turn(self):
        calls=[]
        def post(url, json=None, timeout=None):
            calls.append(json['model'])
            body={"message":{"content":json_module.dumps({
                'education':{'level':'10th','status':'passed','stream':None},
                'occupation':'electrician','skills':['electrical work'],'interests':[],
                'experience':[{'domain':'electrical','duration_months':12}],
                'location':{'state':None,'district':None},'employment_preference':'job',
                'training_willingness':None,'mobility_km':None,'language':'te'
            })}}
            return FakeResponse(body)
        import json as json_module
        ex=OllamaProfileExtractor(model='gemma3:4b', request_post=post)
        ex._selected_model='gemma3:1b'
        p=ex.extract('free form profile', None, 'te')
        self.assertEqual(calls[0], 'gemma3:4b')
        self.assertEqual(p.occupation, 'electrician')
        self.assertEqual(p.experience[0].duration_months, 12)

    def test_fast_model_used_for_focused_location_turn(self):
        calls=[]
        def post(url, json=None, timeout=None):
            calls.append(json['model'])
            return FakeResponse({"message":{"content":json_module.dumps({
                'education':{'level':'wrong','status':'passed','stream':None},
                'occupation':'wrong','skills':['wrong'],'interests':['Hyderabad'],
                'experience':[], 'location':{'state':'Telangana','district':'Hyderabad'},
                'employment_preference':'job','training_willingness':False,
                'mobility_km':None,'language':'hi'
            })}})
        import json as json_module
        current=BeneficiaryProfile(
            education=Education(level='10th', status='passed'), occupation='electrician',
            experience=[Experience(domain='electrical', duration_months=12)], employment_preference='job'
        )
        ex=OllamaProfileExtractor(model='gemma3:4b', request_post=post)
        ex._selected_model='gemma3:1b'
        p=ex.extract('Hyderabad', current, 'hi')
        self.assertEqual(calls[0], 'gemma3:1b')
        self.assertEqual(p.occupation, 'electrician')
        self.assertEqual(p.location.district, 'Hyderabad')
        self.assertIsNone(p.training_willingness)


if __name__ == '__main__':
    unittest.main()
