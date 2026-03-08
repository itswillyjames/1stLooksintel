"""Export Pydantic models."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any


class ExportRenderRequest(BaseModel):
    template_version: str = "v1"
    idempotency_key: Optional[str] = None


class ExportManifest(BaseModel):
    """Manifest JSON schema for export."""
    model_config = ConfigDict(extra="ignore")
    
    export_id: str
    report_version_id: str
    export_type: str
    template_version: str
    rendered_at: str
    
    # References to source data
    stage_attempts: List[Dict[str, Any]]  # {stage_name, attempt_id, output_id, status}
    entities: List[Dict[str, Any]]  # {entity_id, canonical_name, role}
    entity_suggestions: List[Dict[str, Any]]  # {suggestion_id, observed_name, status}
    evidence_links: List[Dict[str, Any]]  # {evidence_id, link_type, link_id}
    
    # Snapshot reference
    permit_snapshot: Dict[str, Any]
    run_config_snapshot: Dict[str, Any]


class Export(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    
    id: str = Field(alias="_id")
    report_version_id: str
    export_type: str
    template_version: str
    status: str
    html_content: Optional[str] = None
    manifest: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None
    created_at: str
    updated_at: str


class ExportListResponse(BaseModel):
    report_version_id: str
    exports: List[Export]
