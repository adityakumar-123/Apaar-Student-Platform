from datetime import date
from typing import Optional
from pydantic import BaseModel, ConfigDict, field_validator


class StudentCreate(BaseModel):
    apaar_id: str
    name: str
    dob: date
    category: Optional[str] = None
    nationality: Optional[str] = "Indian"
    is_nri: bool = False
    is_oci: bool = False
    is_foreign_national: bool = False

    @field_validator("apaar_id")
    @classmethod
    def check_apaar(cls, v):
        if not (v.isdigit() and len(v) == 12):
            raise ValueError("APAAR ID must be exactly 12 digits")
        return v


class StudentOut(StudentCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)