"""
Recommendation Result Domain Model.
Designed for deterministic scoring and transparent explainability.
"""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict
from backend.models.qualification import Qualification
from backend.models.eligibility import EligibilityStatus, EligibilityRoute


class RecommendationResult(BaseModel):
    """
    Container for a single qualification recommendation result with full explainability metadata.
    """
    model_config = ConfigDict(from_attributes=True)

    qualification: Qualification
    eligibility_status: EligibilityStatus
    matched_route: Optional[EligibilityRoute] = None
    relevance_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    score_breakdown: Dict[str, float] = Field(default_factory=dict)
    reasons: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    pmajay_gia_supported: bool = True
    stipend_eligible: bool = True
    free_training_support: bool = True
    scheme_benefits: List[str] = Field(
        default_factory=lambda: [
            "PM-AJAY GIA 100% Skill Training Subsidy",
            "NSQF Government Certification",
            "Monthly Training Stipend & Assessment Support",
        ]
    )
