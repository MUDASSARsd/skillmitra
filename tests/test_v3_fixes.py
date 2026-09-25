from backend.models.beneficiary import BeneficiaryProfile
from backend.nlu.local_extractor import LocalProfileExtractor


def profile_with_skill():
    p=BeneficiaryProfile(); p.skills=['electrical']; return p


def test_contextual_bare_10_education():
    p=profile_with_skill(); p.education.level=None
    out=LocalProfileExtractor().extract('I have completed 10', p, 'en')
    assert out.education.level == '10th'
    assert out.education.status == 'passed'


def test_ten_class_stt_variant():
    p=profile_with_skill(); p.education.level=None
    out=LocalProfileExtractor().extract('Completed I have completed Tena class', p, 'en')
    # ASR variant Tena is intentionally handled below via context normalization test expectation.
    assert out.education.level == '10th'


def test_diploma_education():
    p=profile_with_skill(); p.education.level=None
    out=LocalProfileExtractor().extract('I studied diploma', p, 'en')
    assert out.education.level == 'Diploma'
    assert out.education.status == 'passed'


def test_hindi_training_ha_variant():
    p=BeneficiaryProfile(); p.education.level='10th'; p.skills=['electrical']; p.experience=[]; p.employment_preference='business'; p.location.district='Hyderabad'
    # next missing field is experience before training in normal order; give an experience marker so training becomes next.
    from backend.models.beneficiary import Experience
    p.experience=[Experience(domain='electrical', duration_months=12)]
    out=LocalProfileExtractor().extract('हा मैं चाहूँगा', p, 'hi')
    assert out.training_willingness is True
