from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class SkillSignal(BaseModel):
    skill: str
    source_type: str
    source_text: Optional[str] = None


class SkillMatch(BaseModel):
    required_skill: str
    user_evidence: str
    match_type: str


class SkillGapAnalysis(BaseModel):
    qualification_code: Optional[str] = None
    qualification_title: str
    user_skill_evidence: List[str] = Field(default_factory=list)
    required_skill_signals: List[SkillSignal] = Field(default_factory=list)
    matched_skills: List[SkillMatch] = Field(default_factory=list)
    partial_matches: List[SkillMatch] = Field(default_factory=list)
    not_evidenced_skills: List[str] = Field(default_factory=list)
    market_skill_signals: List[str] = Field(default_factory=list)
    priority_gaps: List[str] = Field(default_factory=list)
    profile_skill_coverage_percent: float = 0.0
    evidence_quality: str = "LIMITED"
    warnings: List[str] = Field(default_factory=list)
