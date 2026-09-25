"""Deterministic, conservative NQR eligibility evaluation.

Only evaluates constraints that are represented in BeneficiaryProfile. Unknown facts never
become positive evidence. A qualification is eligible when ANY route is fully satisfied.
"""
from __future__ import annotations
import re, sqlite3
from dataclasses import dataclass, field
from typing import Optional
from backend.models.beneficiary import BeneficiaryProfile
from backend.models.eligibility import EligibilityRoute, EligibilityStatus

@dataclass
class RouteEvaluation:
    route: EligibilityRoute
    satisfied: bool = False
    impossible: bool = False
    missing_information: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

@dataclass
class EligibilityEvaluation:
    code: str
    status: EligibilityStatus
    matched_route: Optional[EligibilityRoute] = None
    route_evaluations: list[RouteEvaluation] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

class EligibilityEngine:
    SIMPLE_LEVELS = {"illiterate":0,"5th":5,"8th":8,"9th":9,"10th":10,"11th":11,"12th":12}

    def __init__(self, db_path: str, enable_nsqf_fallback: bool = True):
        self.db_path = db_path
        self.enable_nsqf_fallback = enable_nsqf_fallback

    def _routes(self, code: str) -> list[EligibilityRoute]:
        con=sqlite3.connect(self.db_path); con.row_factory=sqlite3.Row
        rows=con.execute("SELECT * FROM eligibility_routes WHERE code=? ORDER BY route_number",(code,)).fetchall(); con.close()
        return [EligibilityRoute.model_validate(dict(r)) for r in rows]

    @staticmethod
    def _norm(s): return re.sub(r"\s+"," ",(s or "").strip().lower())

    def _simple_grade(self, s):
        s=self._norm(s)
        for k,v in self.SIMPLE_LEVELS.items():
            if re.search(rf"(?<!\d){re.escape(k)}(?!\d)",s): return v
        return None

    def _education_check(self, profile, route, ev):
        req=self._norm(route.criteria_1); have=self._norm(profile.education.level)
        if not req: return
        if not have:
            ev.missing_information.append("education level"); return
        # Previous NSQF qualification is not represented in the current profile schema.
        if "previous nsqf" in req:
            ev.missing_information.append("previous NSQF qualification/level"); return
        rg,hg=self._simple_grade(req),self._simple_grade(have)
        # Compound diploma requirements must be checked before incidental grade text (e.g. "after 10th").
        if "diploma" in req:
            if "diploma" not in have: ev.impossible=True; ev.reasons.append(f"requires {route.criteria_1}")
            elif "3 year" in req and "3 year" not in have and "3-year" not in have: ev.missing_information.append("diploma duration")
            else: ev.reasons.append(f"education matches {route.criteria_1}")
        elif rg is not None:
            if hg is not None:
                if hg < rg: ev.impossible=True; ev.reasons.append(f"education below required {route.criteria_1}")
                else: ev.reasons.append(f"education satisfies {route.criteria_1}")
            elif any(x in have for x in ("diploma","graduate","degree","bachelor","postgraduate")):
                ev.reasons.append(f"higher education satisfies {route.criteria_1}")
            else: ev.missing_information.append(f"education equivalence for {route.criteria_1}")
        else:
            ev.missing_information.append(f"verification of education requirement: {route.criteria_1}")

    def _criteria2_check(self, profile, route, ev):
        c=self._norm(route.criteria_2)
        if not c or c in ("passed","pass","completed"): return
        if "engg" in c or "engineering" in c or "science" in c:
            stream=self._norm(profile.education.stream)
            if not stream: ev.missing_information.append("education stream/course"); return
            if not any(x in stream for x in ("engg","engineering","science")):
                ev.impossible=True; ev.reasons.append(f"education stream does not satisfy {route.criteria_2}")
            else: ev.reasons.append(f"education stream satisfies {route.criteria_2}")
        elif "level" in c and "nsqf" in self._norm(route.criteria_1):
            ev.missing_information.append("previous NSQF level")
        else:
            ev.missing_information.append(f"verification of criterion: {route.criteria_2}")

    def _experience_check(self, profile, route, ev):
        txt=self._norm(route.experience); req=route.experience_months
        if not txt: return
        if "no experience" in txt: return
        # Duration requirement exists; current schema cannot reliably prove domain-specific route experience,
        # so compare known experience durations conservatively.
        known=[x.duration_months for x in profile.experience if x.duration_months is not None]
        if not known:
            ev.missing_information.append(f"experience duration (requires {route.experience})"); return
        if max(known) < req:
            ev.impossible=True; ev.reasons.append(f"experience {max(known)} months is below required {req} months")
        else: ev.reasons.append(f"experience duration satisfies {route.experience}")

    def _training_check(self, profile, route, ev):
        if route.training_qualification:
            # BeneficiaryProfile has no prior-training/NTC field yet: never guess.
            ev.missing_information.append(f"training qualification: {route.training_qualification}")

    def evaluate_route(self, profile, route):
        ev=RouteEvaluation(route=route)
        self._education_check(profile,route,ev); self._criteria2_check(profile,route,ev)
        self._experience_check(profile,route,ev); self._training_check(profile,route,ev)
        ev.satisfied=not ev.impossible and not ev.missing_information
        return ev

    def _nsqf_standard_fallback_route(self, code: str) -> Optional[EligibilityRoute]:
        """Synthesizes an NSQF Level Standard Route when explicit routes.csv entries are missing."""
        try:
            con = sqlite3.connect(self.db_path)
            con.row_factory = sqlite3.Row
            row = con.execute("SELECT nsqf_level_numeric, level FROM qualifications WHERE code = ?", (code,)).fetchone()
            con.close()
            if not row:
                return None
            level = row["nsqf_level_numeric"]
            if level is None:
                level = 3.0
            
            if level <= 3.0:
                c1, exp, exp_m = "8th", "No Experience", 0
            elif level == 4.0:
                c1, exp, exp_m = "10th", "No Experience", 0
            elif level == 5.0:
                c1, exp, exp_m = "12th", "1 year", 12
            else:
                c1, exp, exp_m = "Diploma", "2 years", 24

            return EligibilityRoute(
                code=code,
                route_number=1,
                criteria_1=c1,
                criteria_2="passed",
                experience=exp,
                experience_months=exp_m,
                source_file="nsqf_level_standard_fallback"
            )
        except Exception:
            return None

    def evaluate(self, profile: BeneficiaryProfile, code: str) -> EligibilityEvaluation:
        routes = self._routes(code)
        is_fallback = False
        if not routes:
            if self.enable_nsqf_fallback:
                fb = self._nsqf_standard_fallback_route(code)
                if fb:
                    routes = [fb]
                    is_fallback = True
            if not routes:
                return EligibilityEvaluation(code=code, status=EligibilityStatus.ELIGIBILITY_DATA_MISSING,
                                             reasons=["No verified eligibility routes are stored for this qualification."])
        evals = [self.evaluate_route(profile, r) for r in routes]
        for e in evals:
            if e.satisfied:
                r_text = f"Verified through NSQF Level standard guideline route." if is_fallback else f"Verified through route {e.route.route_number}."
                return EligibilityEvaluation(code=code, status=EligibilityStatus.ELIGIBLE, matched_route=e.route,
                                             route_evaluations=evals, reasons=[r_text])
        # If any route remains possible but lacks facts, don't falsely reject.
        if any(not e.impossible for e in evals):
            missing = []
            for e in evals:
                if not e.impossible:
                    missing.extend(e.missing_information)
            return EligibilityEvaluation(code=code, status=EligibilityStatus.NEEDS_MORE_INFORMATION,
                                         route_evaluations=evals, reasons=list(dict.fromkeys(missing)))
        return EligibilityEvaluation(code=code, status=EligibilityStatus.NOT_ELIGIBLE,
                                     route_evaluations=evals, reasons=["Known profile facts do not satisfy any verified route."])
