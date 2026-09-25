"""
Qualification Domain Model.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class Qualification(BaseModel):
    """
    Represents an official NQR qualification mapped cleanly to Phase 1 SQLite database.
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    s_no: int
    title: str
    code: Optional[str] = None
    description: Optional[str] = None
    sector_name: Optional[str] = None
    level: Optional[str] = None
    nsqf_level_numeric: Optional[float] = None
    max_notational_hours: Optional[str] = None
    min_notational_hours: Optional[str] = None
    version: Optional[str] = None
    originally_approved: Optional[str] = None
    valid_till: Optional[str] = None
    awarding_body: Optional[str] = None
    certifying_bodies: Optional[str] = None
    proposed_occupation: Optional[str] = None
    progression_pathway: Optional[str] = None
    qualification_type: Optional[str] = None
    adopted_qualification: Optional[str] = None
    training_delivery_hours: Optional[str] = None
    is_duplicate_code: int = 0
    source_file: Optional[str] = "Qualifications.xlsx"
    imported_at: Optional[str] = None

    @classmethod
    def from_sqlite_row(cls, row) -> "Qualification":
        """Instantiates a Qualification model directly from a sqlite3.Row object."""
        row_dict = dict(row)
        return cls(**row_dict)
