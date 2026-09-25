from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TrainingCentre(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    centre_id: str
    centre_name: str
    training_partner: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    address: Optional[str] = None
    pincode: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    source: Optional[str] = None
    source_url: Optional[str] = None
    verification_status: str = "UNVERIFIED"
    last_verified_at: Optional[str] = None


class TrainingOffering(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    offering_id: str
    centre_id: str
    qualification_code: Optional[str] = None
    job_role: Optional[str] = None
    sector: Optional[str] = None
    scheme: Optional[str] = None
    batch_id: Optional[str] = None
    delivery_mode: Optional[str] = None
    batch_start_date: Optional[str] = None
    batch_end_date: Optional[str] = None
    batch_timing: Optional[str] = None
    availability_status: str = "UNKNOWN"
    source: Optional[str] = None
    source_url: Optional[str] = None
    last_verified_at: Optional[str] = None


class TrainingOption(BaseModel):
    centre: TrainingCentre
    offering: TrainingOffering
    location_match: str
    currentness: str
