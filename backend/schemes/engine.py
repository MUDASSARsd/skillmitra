from __future__ import annotations
import re
from typing import Any
from backend.models.beneficiary import BeneficiaryProfile
from .store import list_schemes

TRADITIONAL_TRADES = {
    "carpenter","boat maker","armourer","blacksmith","hammer and tool kit maker","locksmith",
    "goldsmith","potter","sculptor","stone carver","stone breaker","cobbler","shoesmith",
    "footwear artisan","mason","basket maker","mat maker","broom maker","coir weaver",
    "doll maker","toy maker","barber","garland maker","washerman","tailor","fishing net maker"
}

def _norm(s: str|None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()

def _is_sc(profile: BeneficiaryProfile) -> bool:
    return _norm(profile.community_category) in {"sc","scheduled caste","scheduled castes"}

def _trade_match(profile: BeneficiaryProfile) -> str|None:
    text = " ".join([profile.occupation or "", *profile.skills, *profile.interests]).lower()
    for t in sorted(TRADITIONAL_TRADES, key=len, reverse=True):
        if t in text:
            return t
    return None

def _self_employment(profile: BeneficiaryProfile) -> bool:
    p=_norm(profile.employment_preference)
    return any(x in p for x in ("self employ","business","entrepreneur","own business","enterprise"))

def _age(profile):
    return getattr(profile, "age", None)

def _income(profile):
    return getattr(profile, "annual_family_income", None)

def match_schemes(profile: BeneficiaryProfile, db_path=None) -> list[dict[str,Any]]:
    schemes=list_schemes(db_path) if db_path else list_schemes()
    results=[]
    sc=_is_sc(profile); age=_age(profile); income=_income(profile)
    rural=_norm(getattr(profile,"area_type",None)) == "rural"
    trade=_trade_match(profile); self_emp=_self_employment(profile)
    for s in schemes:
        code=s["scheme_code"]
        status="INFO_NEEDED"; reasons=[]; missing=[]; cautions=[]
        if code=="PM-AJAY-GIA":
            if sc:
                status="PROGRAM_RELEVANT"
                reasons.append("Profile is marked Scheduled Caste, matching the scheme's target community.")
                reasons.append("GIA supports district/state livelihood projects including skill development and livelihood generation.")
            else:
                status="NOT_MATCH"
                reasons.append("PM-AJAY is targeted to Scheduled Caste communities.")
            cautions.append("This is project/program-level support; it is not represented as a direct individual cash-benefit application.")
        elif code=="PM-DAKSH":
            if not sc:
                status="POSSIBLE_MATCH"; reasons.append("PM-DAKSH also covers some non-SC target groups, but category-specific checks are required.")
            elif age is None:
                status="INFO_NEEDED"; reasons.append("Scheduled Caste category matches."); missing.append("age (official target range: 18-45 years)")
            elif 18 <= age <= 45:
                status="LIKELY_MATCH"; reasons += ["Scheduled Caste category matches.", "Age is within the official 18-45 target range."]
            else:
                status="NOT_MATCH"; reasons.append("Age is outside the official 18-45 target range.")
            if sc: reasons.append("Official PM-DAKSH information states no income limit for SC applicants.")
            missing += [x for x in ["Aadhaar/SIDH registration confirmation"] if status!="NOT_MATCH"]
        elif code=="DDU-GKY":
            if age is not None and not (15 <= age <= 35):
                status="NOT_MATCH"; reasons.append("Age is outside the DDU-GKY 15-35 focus range.")
            else:
                status="POSSIBLE_MATCH"
                if age is None: missing.append("age (DDU-GKY focuses on 15-35)")
                else: reasons.append("Age is within the DDU-GKY 15-35 focus range.")
                if rural: reasons.append("Profile is marked rural.")
                else: missing.append("confirmation that the beneficiary is from a rural poor family / eligible rural household")
        elif code=="PM-VISHWAKARMA":
            if trade is None:
                status="NOT_MATCH"; reasons.append("No occupation/skill matching the scheme's 18 traditional trades was found in the profile.")
            elif age is not None and age < 18:
                status="NOT_MATCH"; reasons.append("Applicant is below 18.")
            else:
                status="POSSIBLE_MATCH"; reasons.append(f"Profile matches the traditional trade: {trade}.")
                if age is None: missing.append("age (must be at least 18)")
                else: reasons.append("Age meets the 18+ requirement.")
                missing.append("family/occupation verification and CSC registration checks")
        elif code=="PMEGP":
            if age is not None and age < 18:
                status="NOT_MATCH"; reasons.append("Applicant is below 18.")
            elif self_emp:
                status="POSSIBLE_MATCH"; reasons.append("Profile indicates self-employment/business preference.")
                if age is None: missing.append("age (must be above 18)")
                missing.append("new-enterprise/project-cost and prior-subsidy checks")
            else:
                status="INFO_NEEDED"; missing.append("whether the beneficiary wants to start a new self-employment enterprise")
        score={"LIKELY_MATCH":4,"PROGRAM_RELEVANT":3,"POSSIBLE_MATCH":2,"INFO_NEEDED":1,"NOT_MATCH":0}[status]
        results.append({
            "scheme_code":code,"scheme_name":s["scheme_name"],"status":status,"evidence_score":score,
            "reasons":reasons,"missing_information":missing,"cautions":cautions,
            "benefits":s.get("benefits"),"application_method":s.get("application_method"),
            "official_url":s.get("official_url"),"source_url":s.get("source_url"),
            "source_checked_on":s.get("source_checked_on")
        })
    results.sort(key=lambda x:(-x["evidence_score"], x["scheme_name"]))
    return results
