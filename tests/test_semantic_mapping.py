import tempfile
import unittest
from pathlib import Path
import numpy as np

from backend.mapping.semantic_retriever import (
    profile_semantic_query, qualification_document, SemanticNQRIndex,
    SemanticNQRCandidateRetriever, HybridSemanticNQRCandidateRetriever,
)
from backend.mapping.retriever import NQRCandidateRetriever
from backend.models.beneficiary import BeneficiaryProfile, Experience
from backend.models.qualification import Qualification


class FakeEmbedder:
    model = "fake-multilingual"
    def status(self): return {"ready": True, "model": self.model, "detail": "ready"}
    def embed(self, inputs, timeout=120):
        out=[]
        for text in inputs:
            t=text.lower()
            # deterministic semantic-ish axes only for exercising vector/index plumbing
            v=np.array([
                sum(k in t for k in ("mason","brick","construction","house","wall")),
                sum(k in t for k in ("electric","wiring","electrician")),
                sum(k in t for k in ("tailor","sewing","garment","stitch")),
                sum(k in t for k in ("solar","photovoltaic")),
            ],dtype=np.float32)
            if not v.any(): v[-1]=0.01
            v=v/max(np.linalg.norm(v),1e-9)
            out.append(v)
        return np.vstack(out)


class FakeIndex:
    def __init__(self, matches): self.matches=matches
    def search(self, query, limit=60): return self.matches[:limit]
    class E: model="fake"
    embedder=E()


class TestSemanticMapping(unittest.TestCase):
    def test_freeform_profile_query_preserves_meaning(self):
        p=BeneficiaryProfile(
            occupation="I build houses with my father",
            skills=["laying bricks"],
            experience=[Experience(domain="residential construction", duration_months=24)],
        )
        q=profile_semantic_query(p)
        self.assertIn("I build houses with my father", q)
        self.assertIn("laying bricks", q)
        self.assertIn("residential construction", q)

    def test_official_document_contains_core_fields(self):
        q=Qualification(s_no=1,title="Brick Mason",description="Builds walls",sector_name="Construction",proposed_occupation="Masonry")
        doc=qualification_document(q)
        self.assertIn("Brick Mason",doc); self.assertIn("Construction",doc); self.assertIn("Builds walls",doc)

    def test_semantic_index_build_load_search(self):
        with tempfile.TemporaryDirectory() as td:
            cache=Path(td)/"idx.npz"
            idx=SemanticNQRIndex(cache_path=cache, embedder=FakeEmbedder())
            st=idx.build(batch_size=200)
            self.assertTrue(st.ready)
            self.assertEqual(st.count,2814)
            got=idx.search("I build houses and walls",limit=10)
            self.assertTrue(got)
            # Verify at least one top row is genuinely masonry/construction related.
            from backend.database.db import get_db_connection
            conn=get_db_connection()
            ids=[x[0] for x in got]
            rows=conn.execute(f"select title,sector_name from qualifications where id in ({','.join('?'*len(ids))})",ids).fetchall()
            conn.close()
            blob=' '.join((r['title']+' '+(r['sector_name'] or '')).lower() for r in rows)
            self.assertTrue(any(k in blob for k in ('mason','construction','brick')))

    def test_semantic_retriever_returns_real_nqr_rows(self):
        # 489 is Brick Mason- Basic in the shipped DB.
        r=SemanticNQRCandidateRetriever(index=FakeIndex([(489,0.92)])).retrieve(
            BeneficiaryProfile(occupation="I build houses"),5)
        self.assertEqual(r[0].qualification.id,489)
        self.assertIn("semantic",r[0].source)

    def test_hybrid_falls_back_to_fts_when_semantic_unavailable(self):
        class Broken:
            def retrieve(self,*a,**k): raise RuntimeError("no index")
        h=HybridSemanticNQRCandidateRetriever(semantic=Broken(),lexical=NQRCandidateRetriever())
        r=h.retrieve(BeneficiaryProfile(occupation="electrician",skills=["electrical wiring"]),5)
        self.assertTrue(r)
        self.assertEqual(h.last_mode,"lexical_fallback")

if __name__ == '__main__': unittest.main()
