"""Real-laptop smoke tests for open-vocabulary NQR semantic mapping.
Run only after BUILD_SEMANTIC_INDEX.bat succeeds.
"""
from backend.mapping.semantic_retriever import SemanticNQRCandidateRetriever
from backend.models.beneficiary import BeneficiaryProfile, Experience

CASES = [
    ("I build houses and walls", ["mason", "construction", "brick", "concrete"]),
    ("I repair water pumps used on farms", ["pump", "mechanic", "agriculture", "irrigation"]),
    ("I install tiles and marble in houses", ["tile", "mason", "stone"]),
    ("I take care of cows and buffaloes", ["dairy", "animal", "livestock", "cattle"]),
    ("I make wooden furniture", ["carpenter", "furniture", "wood"]),
    ("I repair motorcycles and scooters", ["two wheeler", "automotive", "mechanic", "service"]),
    ("I paint houses and buildings", ["painter", "painting", "construction"]),
    ("I stitch school uniforms and clothes", ["tailor", "sewing", "garment", "apparel"]),
    ("I make bread and cakes in a bakery", ["bakery", "baker", "food"]),
    ("I install rooftop solar panels", ["solar", "photovoltaic", "renewable"]),
]

r = SemanticNQRCandidateRetriever()
st = r.index.status()
if not st.ready:
    print(f"Skipping semantic smoke test: {st.detail}")
    import sys
    if "pytest" in sys.modules:
        import pytest
        pytest.skip(st.detail, allow_module_level=True)
    else:
        sys.exit(0)

failed = 0
for text, expected in CASES:
    p = BeneficiaryProfile(occupation=text, skills=[text])
    got = r.retrieve(p, 8)
    titles = " | ".join((x.qualification.title + " " + (x.qualification.proposed_occupation or "") + " " + (x.qualification.sector_name or "")).lower() for x in got)
    ok = any(k in titles for k in expected)
    print(("PASS" if ok else "CHECK"), "-", text)
    for x in got[:5]:
        print(f"   {x.retrieval_score:.3f}  {x.qualification.title}")
    if not ok:
        failed += 1
print(f"\nSemantic smoke test: {len(CASES)-failed}/{len(CASES)} automatic expectation checks passed.")
if failed:
    print("Some cases need human review; semantic relevance is not a hard classification label.")
