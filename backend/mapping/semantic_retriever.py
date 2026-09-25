"""Semantic NQR retrieval using a local multilingual Ollama embedding model.

The embedding model never decides eligibility or fabricates qualifications. It only
maps a free-form livelihood description to semantically similar rows that already
exist in the official local NQR SQLite database.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import numpy as np
import requests

from backend.database.db import DEFAULT_DB_PATH, get_db_connection
from backend.mapping.retriever import CandidateMatch, NQRCandidateRetriever, profile_signals
from backend.models.beneficiary import BeneficiaryProfile
from backend.models.qualification import Qualification


DEFAULT_MODEL = os.getenv("NQR_EMBED_MODEL", "embeddinggemma")
DEFAULT_MIN_COSINE = float(os.getenv("NQR_SEMANTIC_MIN_COSINE", "0.20"))
DEFAULT_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
_cache_env = os.getenv("NQR_SEMANTIC_CACHE", "").strip()
DEFAULT_CACHE = (Path(_cache_env) if _cache_env else Path(__file__).resolve().parents[2] / "data" / "nqr_semantic_embeddings.npz")


def qualification_document(q: Qualification) -> str:
    """Build a retrieval document only from official NQR fields."""
    parts = [
        f"Qualification: {q.title}" if q.title else "",
        f"Occupation: {q.proposed_occupation}" if q.proposed_occupation else "",
        f"Sector: {q.sector_name}" if q.sector_name else "",
        f"Description: {q.description}" if q.description else "",
        f"Progression: {q.progression_pathway}" if q.progression_pathway else "",
    ]
    return "\n".join(x for x in parts if x).strip()


def profile_semantic_query(profile: BeneficiaryProfile) -> str:
    """Preserve open-vocabulary livelihood meaning; do not classify it into a fixed list."""
    chunks: List[str] = []
    if profile.occupation:
        chunks.append(f"Occupation or work: {profile.occupation}")
    if profile.skills:
        chunks.append("Skills: " + ", ".join(profile.skills))
    exp = [e.domain for e in profile.experience if e.domain]
    if exp:
        chunks.append("Work experience domains: " + ", ".join(exp))
    if profile.interests:
        chunks.append("Work interests: " + ", ".join(profile.interests))
    return "\n".join(chunks).strip()


class OllamaEmbeddingClient:
    def __init__(self, model: str = DEFAULT_MODEL, base_url: str = DEFAULT_BASE_URL, request_post=None, request_get=None):
        self.model = model
        self.base_url = base_url
        self._post = request_post or requests.post
        self._get = request_get or requests.get

    def status(self) -> dict:
        try:
            r = self._get(f"{self.base_url}/api/tags", timeout=4)
            r.raise_for_status()
            names = [m.get("name", "") for m in r.json().get("models", [])]
            ready = any(n == self.model or n.startswith(self.model + ":") for n in names)
            return {"ready": ready, "model": self.model, "detail": "ready" if ready else f"Run: ollama pull {self.model}"}
        except Exception as exc:
            return {"ready": False, "model": self.model, "detail": str(exc)}

    def embed(self, inputs: List[str], timeout: int = 120) -> np.ndarray:
        if not inputs:
            return np.empty((0, 0), dtype=np.float32)
        r = self._post(
            f"{self.base_url}/api/embed",
            json={"model": self.model, "input": inputs, "truncate": True, "keep_alive": "30m"},
            timeout=timeout,
        )
        r.raise_for_status()
        arr = np.asarray(r.json().get("embeddings", []), dtype=np.float32)
        if arr.ndim != 2 or arr.shape[0] != len(inputs):
            raise RuntimeError("Embedding model returned an unexpected response shape.")
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return arr / norms


@dataclass
class SemanticIndexStatus:
    ready: bool
    model: str
    count: int
    cache_path: str
    detail: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class SemanticNQRIndex:
    def __init__(self, db_path=None, cache_path: Optional[Path] = None, embedder: Optional[OllamaEmbeddingClient] = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.cache_path = Path(cache_path or DEFAULT_CACHE)
        self.embedder = embedder or OllamaEmbeddingClient()
        self._ids: Optional[np.ndarray] = None
        self._matrix: Optional[np.ndarray] = None
        self._meta: Dict[str, object] = {}

    def _db_count(self) -> int:
        conn = get_db_connection(self.db_path)
        try:
            return int(conn.execute("SELECT COUNT(*) FROM qualifications").fetchone()[0])
        finally:
            conn.close()

    def load(self) -> bool:
        if self._ids is not None and self._matrix is not None:
            return True
        if not self.cache_path.exists():
            return False
        try:
            data = np.load(self.cache_path, allow_pickle=False)
            ids = data["ids"].astype(np.int64)
            matrix = data["embeddings"].astype(np.float32)
            model = str(data["model"].item())
            count = int(data["qualification_count"].item())
            if model != self.embedder.model or count != self._db_count() or matrix.shape[0] != len(ids):
                return False
            self._ids, self._matrix = ids, matrix
            self._meta = {"model": model, "qualification_count": count}
            return True
        except Exception:
            return False

    def status(self) -> SemanticIndexStatus:
        loaded = self.load()
        model_status = self.embedder.status()
        if loaded:
            return SemanticIndexStatus(True, self.embedder.model, len(self._ids), str(self.cache_path), "Semantic NQR index is ready.")
        detail = "Semantic cache is missing or stale. Run BUILD_SEMANTIC_INDEX.bat."
        if not model_status.get("ready"):
            detail = model_status.get("detail") or detail
        return SemanticIndexStatus(False, self.embedder.model, 0, str(self.cache_path), detail)

    def build(self, batch_size: int = 48, progress=None) -> SemanticIndexStatus:
        st = self.embedder.status()
        if not st.get("ready"):
            raise RuntimeError(st.get("detail") or f"Embedding model {self.embedder.model} is not ready.")
        conn = get_db_connection(self.db_path)
        try:
            rows = conn.execute("SELECT * FROM qualifications ORDER BY id").fetchall()
        finally:
            conn.close()
        quals = [Qualification.from_sqlite_row(r) for r in rows]
        ids = np.asarray([q.id for q in quals], dtype=np.int64)
        vectors: List[np.ndarray] = []
        total = len(quals)
        for start in range(0, total, batch_size):
            batch = quals[start:start + batch_size]
            vectors.append(self.embedder.embed([qualification_document(q) for q in batch]))
            if progress:
                progress(min(start + len(batch), total), total)
        matrix = np.vstack(vectors).astype(np.float32)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            self.cache_path,
            ids=ids,
            embeddings=matrix,
            model=np.asarray(self.embedder.model),
            qualification_count=np.asarray(total, dtype=np.int64),
        )
        self._ids, self._matrix = ids, matrix
        self._meta = {"model": self.embedder.model, "qualification_count": total}
        return SemanticIndexStatus(True, self.embedder.model, total, str(self.cache_path), "Semantic NQR index built successfully.")

    def search(self, query: str, limit: int = 60) -> List[tuple[int, float]]:
        if not query.strip() or limit < 1:
            return []
        if not self.load():
            raise RuntimeError("Semantic NQR index is not ready. Run BUILD_SEMANTIC_INDEX.bat first.")
        qv = self.embedder.embed([query])[0]
        scores = self._matrix @ qv
        n = min(limit, len(scores))
        if n == 0:
            return []
        idx = np.argpartition(-scores, n - 1)[:n]
        idx = idx[np.argsort(-scores[idx])]
        return [(int(self._ids[i]), float(scores[i])) for i in idx]


class SemanticNQRCandidateRetriever:
    def __init__(self, db_path=None, index: Optional[SemanticNQRIndex] = None, min_cosine: float = DEFAULT_MIN_COSINE):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.index = index or SemanticNQRIndex(self.db_path)
        self.min_cosine = max(-1.0, min(1.0, float(min_cosine)))

    def retrieve(self, profile: BeneficiaryProfile, limit: int = 30) -> List[CandidateMatch]:
        query = profile_semantic_query(profile)
        if not query:
            return []
        matches = self.index.search(query, max(limit, 1))
        if not matches:
            return []
        ids = [x[0] for x in matches]
        score_by_id = dict(matches)
        placeholders = ",".join("?" for _ in ids)
        conn = get_db_connection(self.db_path)
        try:
            rows = conn.execute(f"SELECT * FROM qualifications WHERE id IN ({placeholders})", ids).fetchall()
        finally:
            conn.close()
        q_by_id = {q.id: q for q in (Qualification.from_sqlite_row(r) for r in rows)}
        signals = [f"{s}:{p}" for s, p, _ in profile_signals(profile)]
        out = []
        for qid, raw_score in matches:
            q = q_by_id.get(qid)
            if not q or raw_score < self.min_cosine:
                continue
            # Cosine can be negative. Map to [0,1] for the existing recommendation scorer.
            # Low-cosine rows are filtered first so "nearest" never automatically means "relevant".
            bounded = max(0.0, min(1.0, (raw_score + 1.0) / 2.0))
            out.append(CandidateMatch(q, bounded, signals.copy(), {}, source=f"local_nqr_semantic:{self.index.embedder.model}"))
        return out[:limit]


class HybridSemanticNQRCandidateRetriever:
    """Semantic-first retrieval with an explainable FTS boost/fallback."""
    def __init__(self, db_path=None, semantic=None, lexical=None, semantic_weight: float = 0.85):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.semantic = semantic or SemanticNQRCandidateRetriever(self.db_path)
        self.lexical = lexical or NQRCandidateRetriever(self.db_path)
        self.semantic_weight = semantic_weight
        self.last_mode = "uninitialized"

    def retrieve(self, profile: BeneficiaryProfile, limit: int = 30) -> List[CandidateMatch]:
        semantic_results: List[CandidateMatch] = []
        try:
            semantic_results = self.semantic.retrieve(profile, max(limit * 2, 50))
        except Exception:
            semantic_results = []
        lexical_results = self.lexical.retrieve(profile, max(limit * 2, 50))
        if not semantic_results:
            self.last_mode = "lexical_fallback"
            return lexical_results[:limit]

        self.last_mode = "semantic_hybrid"
        merged: Dict[int, CandidateMatch] = {}
        sw = self.semantic_weight
        for c in semantic_results:
            merged[c.qualification.id] = CandidateMatch(
                c.qualification, sw * c.retrieval_score, list(c.matched_signals), dict(c.field_hits), c.source
            )
        for c in lexical_results:
            qid = c.qualification.id
            if qid in merged:
                m = merged[qid]
                m.retrieval_score = min(1.0, m.retrieval_score + (1.0 - sw) * c.retrieval_score)
                m.field_hits = c.field_hits
                m.source = f"{m.source}+fts5"
            else:
                merged[qid] = CandidateMatch(
                    c.qualification, (1.0 - sw) * c.retrieval_score,
                    list(c.matched_signals), dict(c.field_hits), "local_nqr_fts5_only"
                )
        return sorted(merged.values(), key=lambda x: (-x.retrieval_score, x.qualification.title.lower()))[:limit]
