from backend.nlu.local_extractor import LocalProfileExtractor
from backend.nlu.online_extractor import HybridOnlineProfileExtractor
from backend.conversation.session import ConversationManager
from backend.models.beneficiary import BeneficiaryProfile, Education, Experience


def test_hindi_spaced_10vi_and_dashvi_are_normalized():
    ex = LocalProfileExtractor()
    p = ex.extract("मेरा नाम सैयद मुदासिर है, मैं इलेक्ट्रीशियन का काम करता हूँ, एक साल से, मैं 10 वीं कक्षा तक पढ़ा हूँ।", language_code="hi")
    assert p.education.level == "10th"
    assert p.education.status == "passed"
    assert "electrical" in p.skills
    assert p.experience and p.experience[0].duration_months == 12

    p2 = ex.extract("मैने दशवीं कक्षा तक पढ़ा।", language_code="hi")
    assert p2.education.level == "10th"


def test_generic_yes_to_employment_gets_short_clarifier_not_full_loop():
    profile = BeneficiaryProfile(
        education=Education(level="10th", status="passed"),
        skills=["electrical"],
        experience=[Experience(domain="electrical", duration_months=12)],
        language="hi",
    )
    mgr = ConversationManager(LocalProfileExtractor())
    turn = mgr.process("हां मैं चाहता", profile, "hi")
    assert turn.profile.employment_preference is None
    assert "नौकरी" in turn.next_question
    assert "स्वरोज़गार" in turn.next_question
    assert "बिजनेस" in turn.next_question
    assert "इन तीन में से" not in turn.next_question


def test_hybrid_ambiguous_employment_yes_does_not_pay_cloud_or_guess():
    calls=[]
    def fake(prompt, text):
        calls.append(text)
        return '{"education":{"level":null,"status":null,"stream":null},"occupation":null,"skills":[],"interests":[],"experience":[],"location":{"state":null,"district":null},"employment_preference":"job","training_willingness":null,"mobility_km":null,"language":"hi"}'
    profile = BeneficiaryProfile(
        education=Education(level="10th", status="passed"),
        skills=["electrical"],
        experience=[Experience(domain="electrical", duration_months=12)],
        language="hi",
    )
    ex=HybridOnlineProfileExtractor(api_caller=fake, api_key="test")
    out=ex.extract("मैं चाहता", profile, "hi")
    assert calls == []
    assert out.employment_preference is None


def test_hybrid_duplicate_known_fact_stays_fast_without_cloud():
    calls=[]
    def fake(prompt, text):
        calls.append(text)
        raise AssertionError('Gemini should not run for a duplicate fact already understood by rules')
    profile = BeneficiaryProfile(
        education=Education(level="10th", status="passed"),
        skills=["electrical"],
        experience=[Experience(domain="electrical", duration_months=12)],
        language="hi",
    )
    ex=HybridOnlineProfileExtractor(api_caller=fake, api_key="test")
    out=ex.extract("मैं 10th क्लास तक पढ़ा हूँ।", profile, "hi")
    assert calls == []
    assert out.education.level == "10th"
    assert ex.last_mode == "online_fast_rules"
