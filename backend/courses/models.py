from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field

class SkillIndiaCourse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    course_id: str
    code: Optional[str] = None
    readable_code: Optional[str] = None
    title: str
    qp_codes: List[str] = Field(default_factory=list)
    nos_codes: List[str] = Field(default_factory=list)
    nsqf_level: Optional[float] = None
    provider: Optional[str] = None
    provider_id: Optional[str] = None
    program: Optional[str] = None
    initiative: Optional[str] = None
    language: Optional[str] = None
    price: Optional[float] = None
    course_mode: Optional[str] = None
    availability: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    occupation: Optional[str] = None
    domain: Optional[str] = None
    description: Optional[str] = None
    enrollment_count: Optional[int] = None
    rating_average: Optional[float] = None
    age_requirement: Optional[str] = None
    educational_qualification: Optional[str] = None
    industry_experience: Optional[str] = None
    source_url: Optional[str] = None
    fetched_at: Optional[str] = None

class CourseMatch(BaseModel):
    course: SkillIndiaCourse
    match_type: str
    match_score: float
    live_confirmation_required: bool = True
