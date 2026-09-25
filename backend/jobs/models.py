from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class JobOpening(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    job_id: str
    title: str
    company_name: Optional[str] = None
    description: Optional[str] = None
    roles_responsibility: Optional[str] = None
    sector_name: Optional[str] = None
    functional_area: Optional[str] = None
    min_education: Optional[str] = None
    min_experience: Optional[float] = None
    max_experience: Optional[float] = None
    vacancy_count: int = 0
    min_ctc_monthly: Optional[float] = None
    max_ctc_monthly: Optional[float] = None
    min_ctc_annual: Optional[float] = None
    max_ctc_annual: Optional[float] = None
    wage_type: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    country: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    posted_on: Optional[str] = None
    valid_upto: Optional[str] = None
    apply_url: Optional[str] = None
    source_system: Optional[str] = None
    is_active: bool = True
    fetched_at: Optional[str] = None


class JobDemandSummary(BaseModel):
    query: str
    state: Optional[str] = None
    district: Optional[str] = None
    matched_job_postings: int = 0
    total_vacancies: int = 0
    salary_records: int = 0
    median_monthly_salary: Optional[float] = None
    advertised_monthly_min: Optional[float] = None
    advertised_monthly_max: Optional[float] = None
    top_districts: List[dict] = Field(default_factory=list)
    demand_band: str = "NO_DATA"
    latest_posted_on: Optional[str] = None
    source_systems: List[str] = Field(default_factory=list)
    caveat: str = "Demand is based on cached job postings, not the entire labour market. Salary fields are reported as supplied by the source."
