"""
Abstract Profile Extractor Base Class.
Defines the unified interface for both Online and Local profile extraction strategies.
"""
from abc import ABC, abstractmethod
from typing import Optional
from backend.models.beneficiary import BeneficiaryProfile


class ProfileExtractor(ABC):
    """
    Abstract base interface for beneficiary profile extraction.
    Implementations (OnlineProfileExtractor, LocalProfileExtractor) must produce
    identical BeneficiaryProfile output schemas.
    """

    @abstractmethod
    def extract(
        self,
        text: str,
        current_profile: Optional[BeneficiaryProfile] = None,
        language_code: Optional[str] = None
    ) -> BeneficiaryProfile:
        """
        Extracts structured information from unstructured beneficiary input text
        and statefully merges it with the provided current_profile.
        """
        pass
