"""Conservative skill-gap analysis grounded in stored NQR qualification text.

The engine does not ask an LLM to invent requirements. Official requirement signals
come from the imported NQR qualification description. Cached job tags are shown as
separate, time-sensitive market evidence. A skill that is not present in the profile
is labelled *not evidenced*, not assumed absent.
"""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable, Optional

from backend.database.db import DEFAULT_DB_PATH
from backend.models.beneficiary import BeneficiaryProfile
from backend.skill_gap.models import SkillGapAnalysis, SkillSignal, SkillMatch
from backend.jobs.store import job_evidence


_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "with", "by", "as", "at",
    "from", "that", "this", "different", "various", "applicable", "required", "basic", "work",
    "works", "working", "individual", "person", "system", "systems", "component", "components",
}

# Broad vocabulary used only for normalization/matching, never to create a requirement
# unless the concept is present in source text.
_SYNONYM_GROUPS = [
    {"wiring", "wire", "electrical wiring", "cabling", "cable laying", "cables"},
    {"repair", "repairing", "maintenance", "maintain", "servicing", "service"},
    {"install", "installation", "installing", "fitting", "fit"},
    {"test", "testing", "inspection", "inspect", "checking", "check"},
    {"commission", "commissioning"},
    {"troubleshoot", "troubleshooting", "fault finding", "diagnostics", "diagnosis"},
    {"safety", "safe", "safety procedures", "safety requirements"},
    {"solar pv", "photovoltaic", "pv", "solar panel", "solar panels", "solar module", "solar modules"},
    {"earthing", "grounding"},
    {"inverter", "inverter installation"},
    {"customer service", "customer handling", "client service", "client handling"},
    {"sales", "selling", "retail sales"},
    {"fabrication", "fabricate"},
    {"welding", "weld"},
    {"assembly", "assemble"},
    {"operate", "operation", "machine operation", "operating"},
]

_ACTION_RE = re.compile(
    r"\b(?:install(?:s|ed|ing)?|maintain(?:s|ed|ing)?|repair(?:s|ed|ing)?|test(?:s|ed|ing)?|"
    r"commission(?:s|ed|ing)?|inspect(?:s|ed|ing)?|check(?:s|ed|ing)?|configure(?:s|d|ing)?|"
    r"operate(?:s|d|ing)?|perform(?:s|ed|ing)?|assemble(?:s|d|ing)?|fabricate(?:s|d|ing)?|"
    r"weld(?:s|ed|ing)?|fit(?:s|ted|ting)?|lay(?:s|ing)?|wire(?:s|d|ing)?|troubleshoot(?:s|ed|ing)?|"
    r"service(?:s|d|ing)?|monitor(?:s|ed|ing)?|handle(?:s|d|ing)?|use(?:s|d|ing)?|read(?:s|ing)?|"
    r"design(?:s|ed|ing)?|mount(?:s|ed|ing)?|connect(?:s|ed|ing)?|maintain(?:s|ed|ing)?)\b",
    re.I,
)

# High-value concepts that should be preserved when they occur in official text.
_CONCEPT_PATTERNS = [
    (r"\belectrical wiring\b|\bwiring\b", "electrical wiring"),
    (r"\b(?:electrical )?installation\b|\binstall(?:s|ing)?\b", "installation"),
    (r"\bmaintenance\b|\bmaintain(?:s|ing)?\b", "maintenance"),
    (r"\brepair(?:s|ing)?\b", "repair"),
    (r"\btesting\b|\btests?\b", "testing"),
    (r"\bcommission(?:ing|s)?\b", "commissioning"),
    (r"\binspect(?:ion|s|ing)?\b", "inspection"),
    (r"\btroubleshoot(?:ing|s)?\b|\bfault finding\b", "troubleshooting"),
    (r"\bsafety (?:procedures|requirements|standards|guidelines)\b|\bsafety\b", "safety compliance"),
    (r"\b(?:codes?|standards?|legal regulations?)\b", "codes and standards compliance"),
    (r"\bearthing\b|\bgrounding\b", "earthing / grounding"),
    (r"\binverter(?: installation)?\b", "inverter work"),
    (r"\b(?:solar|photovoltaic|pv) (?:modules?|panels?|systems?)\b", "solar PV systems"),
    (r"\bmounting (?:structures?|systems?)\b|\bmount(?:ing)?\b", "mounting"),
    (r"\bcontrol panel wiring\b", "control panel wiring"),
    (r"\btransformer(?:s)?\b", "transformer maintenance"),
    (r"\bdg sets?\b|\bdiesel generator(?:s)?\b", "DG set operation"),
    (r"\belectrical drawings?\b|\bblueprints?\b", "reading electrical drawings / blueprints"),
    (r"\belectrical (?:and )?hand tools?\b|\bhand tools?\b", "electrical / hand tool use"),
    (r"\bmachine operation\b|\boperate(?:s|d|ing)? (?:[\w -]+ )?machines?\b", "machine operation"),
    (r"\bcustomer (?:service|handling)\b", "customer service"),
    (r"\bsales\b|\bselling\b", "sales"),
    (r"\bwelding\b", "welding"),
    (r"\bfabrication\b", "fabrication"),
    (r"\bassembly\b|\bassemble(?:s|d|ing)?\b", "assembly"),
]


def _norm(text: str) -> str:
    x = str(text or "").casefold()
    x = re.sub(r"[^\w+#]+", " ", x, flags=re.UNICODE)
    return re.sub(r"\s+", " ", x).strip()


def _tokens(text: str) -> set[str]:
    return {t for t in _norm(text).split() if len(t) > 1 and t not in _STOP}


def _canonical_synonym(text: str) -> set[str]:
    n = _norm(text)
    hits = {n} if n else set()
    for group in _SYNONYM_GROUPS:
        if any(_norm(x) in n or n in _norm(x) for x in group if n):
            hits.update(_norm(x) for x in group)
    return hits


def _dedupe(values: Iterable[str]) -> list[str]:
    out, seen = [], set()
    for v in values:
        v = re.sub(r"\s+", " ", str(v or "").strip(" .,:;-/"))
        k = _norm(v)
        if v and k and k not in seen:
            seen.add(k); out.append(v)
    return out


def _action_phrases(text: str) -> list[str]:
    """Extract short action-object phrases directly from source wording."""
    if not text:
        return []
    phrases = []
    # Clause boundaries make this intentionally conservative.
    clauses = re.split(r"[.;]|\bwhile\b|\bwho\b", text)
    for clause in clauses:
        clause = re.sub(r"\s+", " ", clause).strip()
        m = _ACTION_RE.search(clause)
        if not m:
            continue
        frag = clause[m.start():]
        frag = re.split(r",|\band\b|\bthat\b|\bwhich\b|\bby\b", frag, maxsplit=1, flags=re.I)[0]
        words = frag.split()
        if len(words) > 9:
            words = words[:9]
        phrase = " ".join(words).strip(" ,.-")
        tok_count = len(_tokens(phrase))
        if 2 <= tok_count <= 9:
            # Very short generic "perform X" fragments are usually grammar debris, not useful skills.
            if re.match(r"^perform\b", phrase, flags=re.I) and tok_count <= 2:
                continue
            phrases.append(phrase)
    return _dedupe(phrases)


def extract_official_skill_signals(description: str | None) -> list[SkillSignal]:
    """Derive requirement signals only from the imported official description text."""
    text = str(description or "").strip()
    if not text:
        return []
    skills: list[SkillSignal] = []
    for pattern, label in _CONCEPT_PATTERNS:
        m = re.search(pattern, text, flags=re.I)
        if m:
            # Keep a compact source excerpt around the actual match for provenance.
            start, end = max(0, m.start() - 45), min(len(text), m.end() + 70)
            excerpt = re.sub(r"\s+", " ", text[start:end]).strip()
            skills.append(SkillSignal(skill=label, source_type="official_nqr_description", source_text=excerpt))
    for phrase in _action_phrases(text):
        skills.append(SkillSignal(skill=phrase, source_type="official_nqr_description", source_text=phrase))
    # Dedupe by normalized skill, preferring the curated canonical concept.
    out, seen = [], set()
    for s in skills:
        k = _norm(s.skill)
        if k and k not in seen:
            seen.add(k); out.append(s)
    return out[:16]


def _user_evidence(profile: BeneficiaryProfile) -> list[str]:
    values = list(profile.skills)
    # Occupation/experience are kept as broad evidence only. They can create a partial
    # domain match but must not prove a specific task such as commissioning or earthing.
    if profile.occupation:
        values.append(profile.occupation)
    values.extend(x.domain for x in profile.experience if x.domain)
    return _dedupe(values)


def _match(required: str, user: str) -> str | None:
    r, u = _norm(required), _norm(user)
    if not r or not u:
        return None
    if r == u:
        return "exact"
    rs, us = _canonical_synonym(required), _canonical_synonym(user)
    if rs & us and any(len(x.split()) >= 1 for x in rs & us):
        # A generic user skill such as "wiring" is not proof of a specialised task
        # such as "control panel wiring". Keep that as partial evidence.
        rt0, ut0 = _tokens(required), _tokens(user)
        if len(rt0) >= 2 and len(ut0) <= 1 and r != u:
            return "partial"
        if r in u or u in r:
            short = min(len(rt0), len(ut0))
            return "partial" if short <= 1 and r != u else "equivalent"
        return "equivalent"
    rt, ut = _tokens(required), _tokens(user)
    if not rt or not ut:
        return None
    overlap = len(rt & ut)
    if overlap == 0:
        return None
    coverage = overlap / len(rt)
    jaccard = overlap / len(rt | ut)
    if coverage >= 0.8 and jaccard >= 0.5:
        return "token_equivalent"
    if coverage >= 0.4 or jaccard >= 0.3:
        return "partial"
    return None


def _load_qualification(code: str, db_path: str):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT code,title,description,proposed_occupation,sector_name FROM qualifications WHERE lower(trim(code))=lower(trim(?)) LIMIT 1",
            (code,),
        ).fetchone()
    return dict(row) if row else None


class SkillGapEngine:
    def __init__(self, db_path: str | None = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)

    def analyze(self, profile: BeneficiaryProfile, qualification_code: str, *, include_market: bool = True,
                market_limit: int = 10) -> SkillGapAnalysis:
        q = _load_qualification(qualification_code, self.db_path)
        if not q:
            raise ValueError(f"Unknown qualification code: {qualification_code}")

        required = extract_official_skill_signals(q.get("description"))
        evidence = _user_evidence(profile)
        matched: list[SkillMatch] = []
        partial: list[SkillMatch] = []
        not_evidenced: list[str] = []

        for signal in required:
            best = None
            best_rank = -1
            ranks = {"exact": 5, "equivalent": 4, "token_equivalent": 3, "partial": 1}
            for u in evidence:
                mt = _match(signal.skill, u)
                if mt and ranks[mt] > best_rank:
                    best = (u, mt); best_rank = ranks[mt]
            if not best:
                not_evidenced.append(signal.skill)
            elif best[1] == "partial":
                partial.append(SkillMatch(required_skill=signal.skill, user_evidence=best[0], match_type=best[1]))
            else:
                matched.append(SkillMatch(required_skill=signal.skill, user_evidence=best[0], match_type=best[1]))

        market_skills: list[str] = []
        if include_market:
            query = q.get("title") or q.get("proposed_occupation") or ""
            if query:
                ev = job_evidence(
                    query,
                    state=profile.location.state,
                    district=profile.location.district,
                    limit=market_limit,
                    db_path=self.db_path,
                )
                market_skills = _dedupe(tag for job in ev.get("jobs", []) for tag in job.tags)[:20]

        # Prioritise official gaps also mentioned in current job tags, then preserve official order.
        market_norm = " ".join(_norm(x) for x in market_skills)
        priority = sorted(
            not_evidenced,
            key=lambda x: (0 if any(t in market_norm for t in _tokens(x)) else 1, not_evidenced.index(x)),
        )[:6]

        total = len(required)
        weighted = len(matched) + 0.5 * len(partial)
        coverage = round((weighted / total * 100.0), 1) if total else 0.0
        if total >= 5 and evidence:
            quality = "GOOD"
        elif total >= 2:
            quality = "MODERATE"
        else:
            quality = "LIMITED"

        warnings = [
            "A skill not found in the beneficiary profile is 'not evidenced'; SkillMitra does not assume the person lacks it.",
            "Coverage reflects documented profile evidence against skill signals extracted from the stored NQR qualification description; it is not a competency test or employment-readiness probability.",
        ]
        if market_skills:
            warnings.append("Job-market skill signals come from the cached job snapshot and may change; they are kept separate from official NQR evidence.")
        if not required:
            warnings.append("The stored qualification description did not expose enough task-level skill wording for a reliable gap analysis.")

        return SkillGapAnalysis(
            qualification_code=q.get("code"), qualification_title=q.get("title") or qualification_code,
            user_skill_evidence=evidence, required_skill_signals=required,
            matched_skills=matched, partial_matches=partial,
            not_evidenced_skills=_dedupe(not_evidenced), market_skill_signals=market_skills,
            priority_gaps=_dedupe(priority), profile_skill_coverage_percent=coverage,
            evidence_quality=quality, warnings=warnings,
        )
