"""Offline-first NQR candidate retrieval.

Uses only the local SQLite/FTS5 database. It never asks an LLM to invent or
select a qualification. The retriever is intentionally explainable: it builds
queries from beneficiary livelihood signals and scores only official NQR rows.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from backend.database.db import get_db_connection
from backend.models.beneficiary import BeneficiaryProfile
from backend.models.qualification import Qualification

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_STOP = {
    "a","an","and","as","at","be","for","from","i","in","is","it","job","me","my","of","on",
    "or","the","to","want","work","with","ka","ki","ke","hai","hain","mujhe","main","mein","aur",
}

# Small, auditable vocabulary bridge. This is NOT a course map. It only expands
# common beneficiary words into search vocabulary; NQR FTS still decides which
# official qualifications are candidates.
_SYNONYMS: Dict[str, Sequence[str]] = {
    "electrician": ("electrical", "wiring", "electrician"),
    "electrical": ("electrician", "wiring", "electrical"),
    "wiring": ("electrical", "electrician", "wiring"),
    "plumber": ("plumbing", "pipe", "fitting"),
    "plumbing": ("plumber", "pipe", "fitting"),
    "computer": ("computer", "hardware", "networking"),
    "hardware": ("computer", "hardware", "networking"),
    "carpenter": ("carpentry", "wood", "furniture"),
    "welder": ("welding", "fabrication"),
    "tailor": ("tailoring", "sewing", "garment"),
    "driver": ("driving", "driver"),
    "beautician": ("beauty", "salon", "cosmetology"),
    "construction": ("construction", "mason", "masonry", "brick", "concrete"),
    "builder": ("construction", "mason", "masonry", "brick", "concrete"),
    "building": ("construction", "mason", "masonry", "brick", "concrete"),
    "mason": ("mason", "masonry", "brick", "concrete", "construction"),
    "masonry": ("mason", "masonry", "brick", "concrete", "construction"),
    "tailoring": ("tailor", "tailoring", "sewing", "garment"),
    "automotive": ("automotive", "automobile", "mechanic", "vehicle", "motor", "motorcycle", "bike", "two", "wheeler"),
    "mobile": ("mobile", "phone", "handset", "repair"),
    "solar": ("solar", "photovoltaic", "pv", "installer"),
    "cctv": ("cctv", "surveillance", "camera", "security"),
    "retail": ("retail", "sales", "store", "shop"),
    "housekeeping": ("housekeeping", "cleaning", "cleaner"),
    "agriculture": ("agriculture", "farming", "farmer", "crop"),
    "dairy": ("dairy", "milk", "cattle"),
    "security": ("security", "guard"),
    "warehouse": ("warehouse", "storekeeper", "inventory", "packing"),
    "cooking": ("cook", "cooking", "chef", "kitchen"),
    "baking": ("baker", "bakery", "baking"),
    "beauty": ("beauty", "beautician", "salon", "cosmetology"),
    "cctv": ("cctv", "surveillance", "camera", "security"),
}

@dataclass
class CandidateMatch:
    qualification: Qualification
    retrieval_score: float
    matched_signals: List[str] = field(default_factory=list)
    field_hits: Dict[str, int] = field(default_factory=dict)
    source: str = "local_nqr_fts5"

    def as_dict(self) -> dict:
        return {
            "qualification": self.qualification.model_dump(),
            "retrieval_score": round(self.retrieval_score, 4),
            "matched_signals": self.matched_signals,
            "field_hits": self.field_hits,
            "source": self.source,
        }


def _tokens(text: Optional[str]) -> List[str]:
    if not text:
        return []
    out=[]
    for t in _TOKEN_RE.findall(text.lower()):
        if len(t) >= 2 and t not in _STOP and t not in out:
            out.append(t)
    return out


def profile_signals(profile: BeneficiaryProfile) -> List[Tuple[str, str, float]]:
    """Return (source, phrase, weight) without inventing missing information."""
    signals: List[Tuple[str, str, float]] = []
    for x in profile.interests:
        if x.strip(): signals.append(("interest", x.strip(), 1.00))
    for x in profile.skills:
        if x.strip(): signals.append(("skill", x.strip(), 0.95))
    if profile.occupation and profile.occupation.strip():
        signals.append(("occupation", profile.occupation.strip(), 0.95))
    for e in profile.experience:
        if e.domain and e.domain.strip(): signals.append(("experience", e.domain.strip(), 0.85))
    # Deduplicate equivalent phrases while keeping strongest source/weight.
    best={}
    for s,p,w in signals:
        key=p.lower()
        if key not in best or w > best[key][2]: best[key]=(s,p,w)
    return list(best.values())


def _expanded_tokens(phrase: str) -> List[str]:
    base=_tokens(phrase)
    out=list(base)
    for t in base:
        for x in _SYNONYMS.get(t, ()):
            if x not in out: out.append(x)
    return out


class NQRCandidateRetriever:
    """Hybrid lexical retriever over the official local NQR dataset."""
    def __init__(self, db_path=None):
        self.db_path=db_path

    def retrieve(self, profile: BeneficiaryProfile, limit: int = 30) -> List[CandidateMatch]:
        if limit < 1:
            return []
        signals=profile_signals(profile)
        if not signals:
            return []
        conn=get_db_connection(self.db_path)
        aggregate: Dict[int, dict] = {}
        try:
            for source, phrase, weight in signals:
                toks=_expanded_tokens(phrase)
                if not toks: continue
                # OR prevents a long natural phrase from requiring every word.
                query=" OR ".join(f'"{t}"' for t in toks)
                rows=conn.execute("""
                    SELECT q.*, bm25(qualifications_fts, 0.0, 6.0, 2.0, 1.5, 4.0, 5.0) AS rank
                    FROM qualifications_fts
                    JOIN qualifications q ON q.id = qualifications_fts.qualification_id
                    WHERE qualifications_fts MATCH ?
                    ORDER BY rank ASC
                    LIMIT 60
                """, (query,)).fetchall()
                for row in rows:
                    q=Qualification.from_sqlite_row(row)
                    # Convert negative BM25 into bounded positive contribution.
                    lexical=min(1.0, max(0.0, -float(row["rank"]) / 25.0))
                    text_fields={
                        "title": (q.title or "").lower(),
                        "occupation": (q.proposed_occupation or "").lower(),
                        "sector": (q.sector_name or "").lower(),
                        "description": (q.description or "").lower(),
                    }
                    hits={name: sum(1 for t in toks if t in txt) for name,txt in text_fields.items()}
                    exact_bonus=min(0.35, 0.12*hits["title"] + 0.10*hits["occupation"] + 0.05*hits["sector"])
                    contribution=weight*(0.65*lexical + exact_bonus)
                    item=aggregate.setdefault(q.id, {"q":q,"score":0.0,"signals":[],"hits":{}})
                    item["score"] += contribution
                    label=f"{source}:{phrase}"
                    if label not in item["signals"]: item["signals"].append(label)
                    for k,v in hits.items(): item["hits"][k]=item["hits"].get(k,0)+v
        finally:
            conn.close()
        ranked=sorted(aggregate.values(), key=lambda x: (-x["score"], x["q"].title.lower()))[:limit]
        # Normalize against best result for an interpretable retrieval score, not a probability.
        best=ranked[0]["score"] if ranked else 1.0
        return [CandidateMatch(x["q"], min(1.0,x["score"]/best), x["signals"], x["hits"]) for x in ranked]
