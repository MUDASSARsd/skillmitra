"""
Backend Domain Models Package.
Exports all Pydantic schemas and enums for BeneficiaryProfile, Qualification, EligibilityRoute, and RecommendationResult.
"""
from backend.models.eligibility import EligibilityStatus, EligibilityRoute
from backend.models.qualification import Qualification
from backend.models.beneficiary import Education, Experience, Location, BeneficiaryProfile
from backend.models.recommendation import RecommendationResult

__all__ = [
    "EligibilityStatus",
    "EligibilityRoute",
    "Qualification",
    "Education",
    "Experience",
    "Location",
    "BeneficiaryProfile",
    "RecommendationResult"
]
