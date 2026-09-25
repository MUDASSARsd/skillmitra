"""Deterministic profile-completeness checks for the beneficiary conversation."""
from dataclasses import dataclass, field
from typing import List
from backend.models.beneficiary import BeneficiaryProfile


@dataclass(frozen=True)
class CompletenessReport:
    """What is still useful to ask before qualification mapping."""
    missing_critical: List[str] = field(default_factory=list)
    missing_enrichment: List[str] = field(default_factory=list)

    @property
    def ready_for_mapping(self) -> bool:
        return not self.missing_critical


class ProfileCompletenessChecker:
    """Checks facts needed for mapping without pretending optional facts are required."""

    def check(self, profile: BeneficiaryProfile) -> CompletenessReport:
        critical: List[str] = []
        enrichment: List[str] = []

        if not profile.education.level:
            critical.append("education")

        # At least one signal is needed to know what livelihood/qualification family to search.
        if not (profile.interests or profile.skills or profile.occupation):
            critical.append("livelihood_signal")

        # The guided conversation must finish the core beneficiary profile before
        # recommendations are shown.  These used to be only enrichment fields,
        # which allowed NQR results to appear while we were still asking follow-ups.
        if not profile.experience:
            critical.append("experience")
        if profile.employment_preference is None:
            critical.append("employment_preference")
        if not (profile.location.district or profile.location.state):
            critical.append("location")
        if profile.training_willingness is None:
            critical.append("training_willingness")

        return CompletenessReport(critical, enrichment)
