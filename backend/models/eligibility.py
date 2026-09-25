"""
Eligibility Domain Models & Enums.
"""
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class EligibilityStatus(str, Enum):
    """
    Status of beneficiary eligibility for a qualification.
    """
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    ELIGIBILITY_DATA_MISSING = "ELIGIBILITY_DATA_MISSING"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"


class EligibilityRoute(BaseModel):
    """
    Represents an alternative eligibility route for a qualification.
    A beneficiary qualifies if ANY valid route is satisfied.
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    nqr_id: Optional[int] = None
    code: str
    route_number: int
    criteria_1: Optional[str] = None
    criteria_2: Optional[str] = None
    experience: Optional[str] = None
    experience_months: int = Field(default=0, ge=0)
    training_qualification: Optional[str] = None
    source_url: Optional[str] = None
    verification_status: Optional[str] = "UNVERIFIED"
    raw_text: Optional[str] = None
    fetched_at: Optional[str] = None
    source_file: Optional[str] = "eligibility_routes.csv"
    imported_at: Optional[str] = None
