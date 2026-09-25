import unittest
from backend.nlu.local_extractor import LocalProfileExtractor
from backend.models.beneficiary import BeneficiaryProfile

class TestLocalProfileExtractor(unittest.TestCase):
    def setUp(self): self.x=LocalProfileExtractor()
    def test_hinglish_electrical(self):
        p=self.x.extract('Maine 10th pass kiya hai aur 2 saal electrical wiring ka kaam kiya. Hyderabad mein job chahiye.')
        self.assertEqual(p.education.level,'10th'); self.assertEqual(p.experience[0].duration_months,24); self.assertEqual(p.employment_preference,'job')
    def test_unknown_duration_stays_none(self):
        p=self.x.extract('8th ke baad school chhod diya. Papa ke saath kabhi kabhi plumbing ka kaam karta hoon, pipe fitting aata hai.')
        self.assertEqual(p.education.level,'8th'); self.assertEqual(p.education.status,'dropped'); self.assertIsNone(p.experience[0].duration_months)
    def test_duration_without_domain(self):
        p=self.x.extract('I worked for 2 years')
        self.assertEqual(p.experience[0].duration_months,24); self.assertIsNone(p.experience[0].domain)
    def test_no_experience_not_invented(self):
        p=self.x.extract('I completed intermediate and I have never worked before. I want to learn computer hardware.')
        self.assertEqual(p.education.level,'12th'); self.assertEqual(p.experience[0].duration_months,0)
    def test_multiturn(self):
        p=self.x.extract('Mujhe electrician banna hai.')
        p=self.x.extract('10th pass hoon.',p)
        p=self.x.extract('one and half year se wiring ka kaam kar raha hoon.',p)
        self.assertEqual(p.education.level,'10th'); self.assertIn('electrical',p.interests); self.assertEqual(p.experience[0].duration_months,18)

    def test_training_phrase_without_course_word(self):
        p=self.x.extract('karna chahunga')
        self.assertTrue(p.training_willingness)
    def test_training_devanagari_phrase(self):
        p=self.x.extract('करना चाहूंगा')
        self.assertTrue(p.training_willingness)
    def test_training_not_inferred_from_job(self):
        p=self.x.extract('10th pass, electrical job chahiye')
        self.assertIsNone(p.training_willingness)

    def test_real_noisy_hindi_education(self):
        p=self.x.extract('मैं, 10th पास क्या हैं')
        self.assertEqual(p.education.level,'10th'); self.assertEqual(p.education.status,'passed')

    def test_real_noisy_self_employment(self):
        base=BeneficiaryProfile(); base.education.level='10th'; base.skills=['electrical']; base.experience=[]
        # add answered experience so employment is the next field
        from backend.models.beneficiary import Experience
        base.experience=[Experience(domain='electrical',duration_months=24)]
        p=self.x.extract('अम सेल्टे अंप्लोयमेंट और अपना बिजन्यस काना चाहते हैं।',base)
        self.assertEqual(p.employment_preference,'self_employment')

    def test_real_noisy_business(self):
        base=BeneficiaryProfile(); base.education.level='10th'; base.skills=['electrical']
        from backend.models.beneficiary import Experience
        base.experience=[Experience(domain='electrical',duration_months=24)]
        p=self.x.extract('अम अपना बिस्नेच श्रोग करना चाहते है',base)
        self.assertEqual(p.employment_preference,'business')

    def test_hindi_two_years_electrical(self):
        p=self.x.extract('मैं दो साल से लेक्टिक काम कर रहा हूं मुझे जब चाही हैं')
        self.assertEqual(p.experience[0].duration_months,24)
        self.assertEqual(p.experience[0].domain,'electrical')
        self.assertEqual(p.employment_preference,'job')

    def test_telugu_profile_core_fields(self):
        p=self.x.extract('నమస్కారం నేను టెన్త్ పాస్ అయ్యాను నేను ఒక సంవత్సరం నుంచి ఎలక్ట్రీషియన్ పని చేస్తున్నాను నేను నా ఓన్ బిజినెస్ స్టార్ట్ చేయాలి', language_code='te')
        self.assertEqual(p.education.level,'10th')
        self.assertEqual(p.education.status,'passed')
        self.assertIn('electrical',p.skills)
        self.assertEqual(p.experience[0].duration_months,12)
        self.assertEqual(p.employment_preference,'business')
        self.assertEqual(p.language,'te')

if __name__=='__main__': unittest.main()


def test_hindi_training_willingness_full_affirmation():
    from backend.models.beneficiary import BeneficiaryProfile, Education, Experience, Location
    current = BeneficiaryProfile(education=Education(level="10th", status="passed"), skills=["electrical"], experience=[Experience(domain="electrical", duration_months=12)], employment_preference="business", location=Location(district="Hyderabad", state="Telangana"))
    out = LocalProfileExtractor().extract("हाँ मैं चाहूँगा", current, "hi")
    assert out.training_willingness is True

def test_telugu_training_willingness_affirmation():
    from backend.models.beneficiary import BeneficiaryProfile, Education, Experience, Location
    current = BeneficiaryProfile(education=Education(level="10th", status="passed"), skills=["electrical"], experience=[Experience(domain="electrical", duration_months=12)], employment_preference="business", location=Location(district="Hyderabad", state="Telangana"))
    out = LocalProfileExtractor().extract("అవును చేస్తాను", current, "te")
    assert out.training_willingness is True
