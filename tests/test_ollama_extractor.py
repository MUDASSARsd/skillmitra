import json
from unittest.mock import Mock

from backend.models.beneficiary import BeneficiaryProfile, Education
from backend.nlu.ollama_extractor import OllamaProfileExtractor


def fake_response(payload):
    r = Mock()
    r.raise_for_status.return_value = None
    r.json.return_value = {"message": {"content": json.dumps(payload)}}
    return r


def test_free_form_telugu_extraction():
    payload = {
        "education": {"level": "10th class", "status": "passed", "stream": None},
        "occupation": "electrician",
        "skills": ["electrical"],
        "interests": [],
        "experience": [{"domain": "electrical", "duration_months": 12}],
        "location": {"state": None, "district": None},
        "employment_preference": "start own business",
        "training_willingness": None,
        "mobility_km": None,
        "language": "te",
    }
    post = Mock(return_value=fake_response(payload))
    ex = OllamaProfileExtractor(request_post=post)
    p = ex.extract("నేను పదో తరగతి పూర్తి చేశాను...", language_code="te-IN")
    assert p.education.level == "10th"
    assert p.occupation == "electrician"
    assert p.experience[0].duration_months == 12
    assert p.employment_preference == "business"


def test_short_contextual_answer_is_sent_with_question_topic():
    current = BeneficiaryProfile(education=Education(level="10th", status="passed"), skills=["electrical"], experience=[])
    payload = {
        "education": {"level": None, "status": None, "stream": None},
        "occupation": None,
        "skills": [], "interests": [],
        "experience": [{"domain": "electrical", "duration_months": 24}],
        "location": {"state": None, "district": None},
        "employment_preference": None,
        "training_willingness": None,
        "mobility_km": None, "language": None,
    }
    post = Mock(return_value=fake_response(payload))
    ex = OllamaProfileExtractor(request_post=post)
    p = ex.extract("two years", current_profile=current, language_code="en-IN")
    sent = post.call_args.kwargs["json"]["messages"][1]["content"]
    assert "QUESTION_TOPIC=experience" in sent
    assert p.experience[0].duration_months == 24


def test_string_lists_are_coerced():
    payload = {
        "education": "Diploma",
        "occupation": "electrician",
        "skills": "electrician",
        "interests": [],
        "experience": [],
        "location": None,
        "employment_preference": "job",
        "training_willingness": None,
        "mobility_km": None,
        "language": None,
    }
    post = Mock(return_value=fake_response(payload))
    ex = OllamaProfileExtractor(request_post=post)
    p = ex.extract("I studied diploma and work as electrician and want a job")
    assert p.education.level == "Diploma"
    assert p.skills == ["electrician"]
    assert p.employment_preference == "job"


def test_prompt_treats_work_duration_semantically():
    payload = {
        "education": {"level": "12th", "status": None, "stream": None},
        "occupation": "electrical work",
        "skills": ["electrical"],
        "interests": [],
        "experience": [{"domain": "electrical", "duration_months": 18}],
        "location": {"state": None, "district": None},
        "employment_preference": "business",
        "training_willingness": None,
        "mobility_km": None,
        "language": None,
    }
    post = Mock(return_value=fake_response(payload))
    ex = OllamaProfileExtractor(request_post=post)
    p = ex.extract("free-form mixed-language work statement", language_code="hi-IN")
    system = post.call_args.kwargs["json"]["messages"][0]["content"]
    assert "duration_months" in system and "meaning" in system.lower()
    assert p.experience[0].duration_months == 18
    assert p.employment_preference == "business"


def test_dropout_is_preserved_and_stops_reasking_education():
    payload = {
        "education": {"level": "12th", "status": "dropout", "stream": None},
        "occupation": None, "skills": [], "interests": [], "experience": [],
        "location": {"state": None, "district": None},
        "employment_preference": None, "training_willingness": None,
        "mobility_km": None, "language": "te-IN",
    }
    post = Mock(return_value=fake_response(payload))
    ex = OllamaProfileExtractor(request_post=post)
    p = ex.extract("మెను ట్వెల్త్ డ్రాప్ అఔట్", language_code="te-IN")
    assert p.education.level == "12th"
    assert p.education.status == "dropout"
    from backend.conversation.questions import CounterQuestionEngine
    assert CounterQuestionEngine().next_missing_field(p) != "education"


def test_speed_payload_keeps_model_warm_and_limits_generation():
    payload = {
        "education": {"level": "10th", "status": "passed", "stream": None},
        "occupation": None, "skills": [], "interests": [], "experience": [],
        "location": {"state": None, "district": None},
        "employment_preference": None, "training_willingness": None,
        "mobility_km": None, "language": None,
    }
    post = Mock(return_value=fake_response(payload))
    ex = OllamaProfileExtractor(request_post=post)
    current = BeneficiaryProfile(language="te-IN")
    ex.extract("నేను పదో తరగతి పూర్తి చేశాను", current_profile=current, language_code="te-IN")
    sent = post.call_args.kwargs["json"]
    assert sent["keep_alive"] == "30m"
    assert sent["options"]["num_predict"] == 128
    assert sent["options"]["num_ctx"] == 1536
    # compact profile should omit all-null nested structures
    user_msg = sent["messages"][1]["content"]
    assert '"education"' not in user_msg.split("CURRENT_QUESTION_TOPIC")[0]
