from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime
import uuid


class PermitBase(BaseModel):
    city: str
    source_permit_id: str
    filed_date: Optional[str] = None
    issued_date: Optional[str] = None
    address_raw: Optional[str] = None
    address_norm: Optional[str] = None
    work_type: Optional[str] = None
    description_raw: Optional[str] = None
    valuation: Optional[int] = None
    applicant_raw: Optional[str] = None
    contractor_raw: Optional[str] = None
    owner_raw: Optional[str] = None


class PermitCreate(PermitBase):
    pass


class Permit(PermitBase):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    id: str = Field(alias="_id")
    status: str = "new"
    prequal_score: float = 0.0
    prequal_reasons: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class PermitListResponse(BaseModel):
    permits: List[Permit]
    total: int


class PermitSeedRequest(BaseModel):
    force: bool = False


class PermitSeedResponse(BaseModel):
    message: str
    permits_created: int
    already_existed: int
