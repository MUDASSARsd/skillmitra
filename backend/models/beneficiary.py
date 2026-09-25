"""
Beneficiary Profile Models with Stateful Multi-Turn Merge Support.
"""
from typing import Optional, List, Union, Dict, Any
from pydantic import BaseModel, Field


class Education(BaseModel):
    """Education details of a beneficiary."""
    level: Optional[str] = None
    status: Optional[str] = None
    stream: Optional[str] = None

    def merge(self, other: "Education") -> "Education":
        """Updates non-null education fields from another Education instance."""
        if other.level is not None:
            self.level = other.level
        if other.status is not None:
            self.status = other.status
        if other.stream is not None:
            self.stream = other.stream
        return self


class Experience(BaseModel):
    """Work experience entry in a specific domain or duration (supports incomplete info)."""
    domain: Optional[str] = None
    duration_months: Optional[int] = Field(default=None, ge=0)


class Location(BaseModel):
    """Geographic location details of a beneficiary."""
    state: Optional[str] = None
    district: Optional[str] = None

    def merge(self, other: "Location") -> "Location":
        """Updates non-null location fields from another Location instance."""
        if other.state is not None:
            self.state = other.state
        if other.district is not None:
            self.district = other.district
        return self


class BeneficiaryProfile(BaseModel):
    """
    Structured Beneficiary Profile model representing user capabilities, preferences, and background.
    Supports incremental stateful updates across multi-turn dialogues.
    """
    education: Education = Field(default_factory=Education)
    occupation: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    interests: List[str] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    employment_preference: Optional[str] = None
    training_willingness: Optional[bool] = None
    mobility_km: Optional[int] = None
    language: Optional[str] = None
    community_category: Optional[str] = "SC"
    pmajay_target_district: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=0, le=120)
    annual_family_income: Optional[float] = Field(default=None, ge=0)
    area_type: Optional[str] = None  # rural / urban / semi-urban when known
    aadhaar_available: Optional[bool] = None
    bank_account_aadhaar_linked: Optional[bool] = None
    disability_category: Optional[str] = None  # e.g. PwD subtype when explicitly known

    def merge(self, new_data: Union["BeneficiaryProfile", Dict[str, Any]]) -> "BeneficiaryProfile":
        """
        Incrementally merges new profile data into the current profile instance while preserving
        existing non-null / non-empty values.
        """
        if isinstance(new_data, dict):
            incoming = BeneficiaryProfile.model_validate(new_data)
        else:
            incoming = new_data

        # Merge Education
        self.education.merge(incoming.education)

        # Merge scalar fields if non-null in incoming
        if incoming.occupation is not None:
            self.occupation = incoming.occupation
        if incoming.employment_preference is not None:
            self.employment_preference = incoming.employment_preference
        if incoming.training_willingness is not None:
            self.training_willingness = incoming.training_willingness
        if incoming.mobility_km is not None:
            self.mobility_km = incoming.mobility_km
        if incoming.language is not None:
            self.language = incoming.language
        if incoming.community_category is not None:
            self.community_category = incoming.community_category
        if incoming.pmajay_target_district is not None:
            self.pmajay_target_district = incoming.pmajay_target_district
        if incoming.age is not None:
            self.age = incoming.age
        if incoming.annual_family_income is not None:
            self.annual_family_income = incoming.annual_family_income
        if incoming.area_type is not None:
            self.area_type = incoming.area_type
        if incoming.aadhaar_available is not None:
            self.aadhaar_available = incoming.aadhaar_available
        if incoming.bank_account_aadhaar_linked is not None:
            self.bank_account_aadhaar_linked = incoming.bank_account_aadhaar_linked
        if incoming.disability_category is not None:
            self.disability_category = incoming.disability_category

        # Merge Location
        self.location.merge(incoming.location)

        # Merge list fields (skills, interests) maintaining uniqueness
        for skill in incoming.skills:
            if skill not in self.skills:
                self.skills.append(skill)

        for interest in incoming.interests:
            if interest not in self.interests:
                self.interests.append(interest)

        # Merge Experience records (handles incomplete domain/duration entries)
        for new_exp in incoming.experience:
            matched = False
            for existing_exp in self.experience:
                # 1. Both have matching domain
                if existing_exp.domain and new_exp.domain and existing_exp.domain.lower() == new_exp.domain.lower():
                    if new_exp.duration_months is not None:
                        if existing_exp.duration_months is None:
                            existing_exp.duration_months = new_exp.duration_months
                        else:
                            existing_exp.duration_months = max(existing_exp.duration_months, new_exp.duration_months)
                    matched = True
                    break
                # 2. Existing has domain, new has no domain but has duration
                elif existing_exp.domain and not new_exp.domain and new_exp.duration_months is not None:
                    if existing_exp.duration_months is None:
                        existing_exp.duration_months = new_exp.duration_months
                    else:
                        existing_exp.duration_months = max(existing_exp.duration_months, new_exp.duration_months)
                    matched = True
                    break
                # 3. Existing has no domain but has duration, new has domain
                elif not existing_exp.domain and new_exp.domain and existing_exp.duration_months is not None:
                    existing_exp.domain = new_exp.domain
                    if new_exp.duration_months is not None:
                        existing_exp.duration_months = max(existing_exp.duration_months, new_exp.duration_months)
                    matched = True
                    break
                # 4. Both have no domain
                elif not existing_exp.domain and not new_exp.domain:
                    if new_exp.duration_months is not None:
                        existing_exp.duration_months = new_exp.duration_months
                    matched = True
                    break

            if not matched:
                self.experience.append(new_exp)

        return self
