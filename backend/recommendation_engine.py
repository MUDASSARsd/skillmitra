"""Explainable offline recommendation orchestration.

Combines local NQR retrieval with deterministic eligibility evaluation.  The
score is a ranking heuristic, not a probability of suitability or employment.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional

from backend.database.db import DEFAULT_DB_PATH
from backend.eligibility_engine import EligibilityEngine
from backend.mapping.retriever import CandidateMatch, NQRCandidateRetriever, profile_signals
from backend.mapping.semantic_retriever import HybridSemanticNQRCandidateRetriever
from backend.models.beneficiary import BeneficiaryProfile
from backend.models.eligibility import EligibilityStatus
from backend.models.recommendation import RecommendationResult


@dataclass(frozen=True)
class RecommendationWeights:
    retrieval: float = 0.60
    signal_coverage: float = 0.25
    authoritative_field_match: float = 0.15
    eligible_bonus: float = 0.12
    needs_info_penalty: float = 0.04
    not_eligible_penalty: float = 0.60


class RecommendationEngine:
    """Produces ranked NQR recommendations without asking an LLM to choose courses."""
    def __init__(self, db_path=None, retriever=None, eligibility_engine=None, weights=None, enable_nsqf_fallback: bool = True):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        self.retriever = retriever or HybridSemanticNQRCandidateRetriever(self.db_path)
        self.eligibility = eligibility_engine or EligibilityEngine(self.db_path, enable_nsqf_fallback=enable_nsqf_fallback)
        self.weights = weights or RecommendationWeights()

    @staticmethod
    def _clamp(x: float) -> float:
        return max(0.0, min(1.0, x))

    @staticmethod
    def _is_pwd_specific(candidate: CandidateMatch) -> bool:
        """Return True for qualifications explicitly reserved/labeled for PwD/Divyangjan.

        These records are valid official qualifications, but recommending them to a
        beneficiary whose disability status is unknown can be misleading.
        """
        q = candidate.qualification
        hay = f"{q.code or ''} {q.title or ''}".casefold()
        return (
            "scpwd" in hay
            or "divyangjan" in hay
            or "-pwd" in hay
            or "/pwd/" in hay
        )

    @staticmethod
    def _profile_has_pwd_context(profile: BeneficiaryProfile) -> bool:
        if (profile.disability_category or "").strip():
            return True
        # Defense-in-depth for structured callers that placed the information in
        # livelihood text fields before disability_category existed.
        signals = [profile.occupation or "", *(profile.skills or []), *(profile.interests or [])]
        text = " ".join(signals).casefold()
        return any(token in text for token in ("divyang", "disability", "disabled", "person with disability", "pwd"))

    def _score_candidate(self, profile: BeneficiaryProfile, candidate: CandidateMatch):
        signal_types = {s for s, _, _ in profile_signals(profile)}
        matched_types = {x.split(":", 1)[0] for x in candidate.matched_signals if ":" in x}
        coverage = len(signal_types & matched_types) / len(signal_types) if signal_types else 0.0

        # Title and proposed occupation are stronger evidence than a description-only hit.
        hits = candidate.field_hits
        authority = min(1.0, (2 * hits.get("title", 0) + 2 * hits.get("occupation", 0) + hits.get("sector", 0)) / 5.0)
        base = (self.weights.retrieval * candidate.retrieval_score +
                self.weights.signal_coverage * coverage +
                self.weights.authoritative_field_match * authority)
        return base, coverage, authority

    def recommend(self, profile: BeneficiaryProfile, top_k: int = 5, candidate_limit: int = 30) -> List[RecommendationResult]:
        if top_k < 1:
            return []
        candidates = self.retriever.retrieve(profile, max(top_k, candidate_limit))
        results: List[RecommendationResult] = []

        for c in candidates:
            # Do not surface special PwD/Divyangjan variants to the general population
            # unless the beneficiary profile explicitly contains disability context.
            if self._is_pwd_specific(c) and not self._profile_has_pwd_context(profile):
                continue
            q = c.qualification
            if q.code:
                ev = self.eligibility.evaluate(profile, q.code)
                status, matched_route = ev.status, ev.matched_route
            else:
                ev = None
                status, matched_route = EligibilityStatus.ELIGIBILITY_DATA_MISSING, None

            base, coverage, authority = self._score_candidate(profile, c)
            adjustment = 0.0
            if status == EligibilityStatus.ELIGIBLE:
                adjustment += self.weights.eligible_bonus
            elif status == EligibilityStatus.NEEDS_MORE_INFORMATION:
                adjustment -= self.weights.needs_info_penalty
            elif status == EligibilityStatus.NOT_ELIGIBLE:
                adjustment -= self.weights.not_eligible_penalty
            final = self._clamp(base + adjustment)

            reasons = []
            if c.matched_signals:
                readable = [x.split(":", 1)[1] if ":" in x else x for x in c.matched_signals[:4]]
                reasons.append("NQR content matches your stated livelihood signals: " + ", ".join(readable) + ".")
            if c.field_hits.get("title", 0) or c.field_hits.get("occupation", 0):
                reasons.append("The match appears in the qualification title or proposed occupation, not only descriptive text.")
            if status == EligibilityStatus.ELIGIBLE and matched_route:
                reasons.append(f"Verified eligibility route {matched_route.route_number} is satisfied by the known profile facts.")
            elif status == EligibilityStatus.NEEDS_MORE_INFORMATION:
                reasons.append("A potentially valid eligibility route exists, but more beneficiary information is required to verify it.")
            elif status == EligibilityStatus.NOT_ELIGIBLE:
                reasons.append("Known profile facts do not satisfy any currently verified eligibility route.")
            reasons.append("Aligned with PM-AJAY Grants-in-Aid (GIA) component for SC skill empowerment.")

            warnings = []
            if status == EligibilityStatus.ELIGIBILITY_DATA_MISSING:
                warnings.append("Eligibility has NOT been verified because no verified route is stored for this qualification.")
            if status == EligibilityStatus.NEEDS_MORE_INFORMATION and ev:
                for item in ev.reasons[:3]:
                    warnings.append("Eligibility information needed: " + item + ".")
            if q.is_duplicate_code:
                warnings.append("This NQR code is duplicated in the imported source and requires manual verification.")
            warnings.append("Ranking score is an explainable retrieval heuristic, not a probability of suitability, admission, or employment.")

            results.append(RecommendationResult(
                qualification=q,
                eligibility_status=status,
                matched_route=matched_route,
                relevance_score=round(final, 4),
                score_breakdown={
                    "retrieval_relevance": round(c.retrieval_score, 4),
                    "signal_coverage": round(coverage, 4),
                    "authoritative_field_match": round(authority, 4),
                    "eligibility_adjustment": round(adjustment, 4),
                },
                reasons=reasons,
                warnings=warnings,
            ))

        # Relevance stays primary. Eligibility coverage is sparse, so a qualification with
        # missing eligibility data must not be pushed below an unrelated qualification merely
        # because that unrelated row happens to have a verified route. Known-ineligible rows
        # still sort behind otherwise comparable candidates.
        results.sort(key=lambda r: (
            1 if r.eligibility_status == EligibilityStatus.NOT_ELIGIBLE else 0,
            -(r.relevance_score or 0),
            r.qualification.title.lower(),
        ))
        return results[:top_k]
