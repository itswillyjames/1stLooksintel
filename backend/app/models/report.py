from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class ReportCreate(BaseModel):
    permit_id: str


class Report(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    id: str = Field(alias="_id")
    permit_id: str
    status: str
    active_version_id: Optional[str] = None
    created_at: str
    updated_at: str


class ReportWithPermit(Report):
    permit: Optional[Dict[str, Any]] = None


class ReportVersionCreate(BaseModel):
    snapshot_override: Optional[Dict[str, Any]] = None


class ReportVersion(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    id: str = Field(alias="_id")
    report_id: str
    version: int
    snapshot: Dict[str, Any]
    status: str
    created_at: str
    updated_at: str


class StageAttempt(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    id: str = Field(alias="_id")
    report_version_id: str
    stage_name: str
    status: str
    provider: Optional[str] = None
    model_id: Optional[str] = None
    attempt_no: int
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_class: Optional[str] = None
    error_message: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    created_at: str
    updated_at: str


class StageAttemptsResponse(BaseModel):
    report_version_id: str
    stage_attempts: List[StageAttempt]
