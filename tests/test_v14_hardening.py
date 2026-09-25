import requests
import pytest

from backend.nlu.local_extractor import LocalProfileExtractor
from backend.nlu.online_extractor import OnlineProfileExtractor
from backend.models.beneficiary import BeneficiaryProfile
from backend.mapping.semantic_retriever import SemanticNQRCandidateRetriever


def test_offline_masonry_unstructured_english():
    p = LocalProfileExtractor().extract("I help build houses and do brick work")
    assert "masonry" in p.skills


def test_offline_tailoring_telugu():
    p = LocalProfileExtractor().extract("నేను బట్టలు కుట్టుతాను")
    assert "tailoring" in p.skills


def test_offline_bike_repair_telugu():
    p = LocalProfileExtractor().extract("నేను బైక్ రిపేర్ చేస్తాను")
    assert "automotive" in p.skills


def test_offline_agriculture_hindi():
    p = LocalProfileExtractor().extract("मैं किसान हूँ और खेती करता हूँ")
    assert "agriculture" in p.skills


def test_offline_cctv_hinglish():
    p = LocalProfileExtractor().extract("CCTV camera installation ka kaam karta hoon")
    assert "cctv" in p.skills


def test_gemini_network_error_redacts_api_key(monkeypatch):
    secret = "super-secret-key-123"
    def boom(*args, **kwargs):
        req = requests.Request("GET", "https://example.invalid", params={"key": secret}).prepare()
        raise requests.ConnectionError("failed", request=req)
    monkeypatch.setattr(requests, "get", boom)
    x = OnlineProfileExtractor(api_key=secret)
    with pytest.raises(RuntimeError) as ei:
        x._list_models()
    message = str(ei.value)
    assert secret not in message
    assert "Gemini connection failed" in message


class FakeQ:
    id = 1
    title = "Test Qualification"
    proposed_occupation = None
    sector_name = None
    description = None
    progression_pathway = None


class FakeIndex:
    class Embedder:
        model = "fake"
    embedder = Embedder()
    def search(self, query, limit):
        return [(1, 0.10)]


def test_semantic_low_confidence_is_filtered(monkeypatch):
    # Avoid a real DB/Ollama dependency; test only the confidence gate contract.
    from backend.mapping import semantic_retriever as mod
    class Row:
        pass
    class Cursor:
        def fetchall(self): return [Row()]
    class Conn:
        def execute(self, *args, **kwargs): return Cursor()
        def close(self): pass
    monkeypatch.setattr(mod, "get_db_connection", lambda *a, **k: Conn())
    monkeypatch.setattr(mod.Qualification, "from_sqlite_row", classmethod(lambda cls, row: FakeQ()))
    r = SemanticNQRCandidateRetriever(index=FakeIndex(), min_cosine=0.20)
    p = BeneficiaryProfile(skills=["completely unrelated phrase"])
    assert r.retrieve(p, 5) == []
