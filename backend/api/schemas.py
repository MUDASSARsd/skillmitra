from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from backend.models.beneficiary import BeneficiaryProfile
from backend.models.recommendation import RecommendationResult

class RecommendRequest(BaseModel):
    profile: BeneficiaryProfile
    top_k: int = Field(default=5, ge=1, le=10)
    candidate_limit: int = Field(default=30, ge=5, le=100)

class RecommendResponse(BaseModel):
    recommendations: List[RecommendationResult]
    count: int
    mode: str = "offline_deterministic"

class ConversationRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    current_profile: Optional[BeneficiaryProfile] = None
    language_code: Optional[str] = None
    include_recommendations: bool = True
    top_k: int = Field(default=5, ge=1, le=10)

class ConversationResponse(BaseModel):
    profile: BeneficiaryProfile
    ready_for_mapping: bool
    missing_critical: List[str]
    missing_enrichment: List[str]
    next_question: Optional[str]
    recommendations: List[RecommendationResult] = Field(default_factory=list)
    extraction_mode: str = "online_llm"
    timings_ms: Dict[str, float] = Field(default_factory=dict)

class HealthResponse(BaseModel):
    status: str
    database_ready: bool
    qualification_count: int
    eligibility_route_count: int


class TrainingOptionsResponse(BaseModel):
    options: List[dict] = Field(default_factory=list)
    count: int
    data_mode: str = "cached_official_data"
    live_confirmation_required: bool = True

class TrainingStatusResponse(BaseModel):
    training_centres: int
    verified_directory_centres: int = 0
    offerings: int
    open_or_active_offerings: int
    latest_verified_at: Optional[str] = None
    mode: str
    batch_truth: Optional[str] = None


class JobsStatusResponse(BaseModel):
    job_openings: int
    active_job_openings: int
    active_vacancies: int
    latest_fetched_at: Optional[str] = None
    latest_posted_on: Optional[str] = None
    mode: str

class JobsSearchResponse(BaseModel):
    jobs: List[dict] = Field(default_factory=list)
    count: int
    data_mode: str = "cached_live_snapshot"

class JobDemandResponse(BaseModel):
    summary: dict
    data_mode: str = "cached_live_snapshot"


class SkillGapRequest(BaseModel):
    profile: BeneficiaryProfile
    qualification_code: str = Field(min_length=1, max_length=160)
    include_market: bool = True
    market_limit: int = Field(default=10, ge=1, le=50)
