"""Export API endpoints."""

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse, HTMLResponse
from typing import Optional
from app.db import get_db
from app.models.export import ExportRenderRequest, Export, ExportListResponse
from app.services.export_service import render_dossier_export, get_export, list_exports
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exports", tags=["exports"])


@router.get("/{export_id}")
async def get_export_endpoint(
    export_id: str = Path(...),
    format: Optional[str] = Query("json", description="Response format: json or html")
):
    """Get export by ID.
    
    Returns the export record including manifest and HTML content.
    
    - **export_id**: Export ID
    - **format**: Response format - 'json' (default) or 'html' (returns raw HTML)
    """
    db = get_db()
    
    export = await get_export(db, export_id)
    if not export:
        raise HTTPException(status_code=404, detail=f"Export {export_id} not found")
    
    if format == "html" and export.get("html_content"):
        return HTMLResponse(content=export["html_content"])
    
    # Return JSON (exclude _id, use id)
    return JSONResponse(content={
        "id": export["_id"],
        "report_version_id": export["report_version_id"],
        "export_type": export["export_type"],
        "template_version": export["template_version"],
        "status": export["status"],
        "html_content": export.get("html_content"),
        "manifest": export.get("manifest"),
        "idempotency_key": export.get("idempotency_key"),
        "created_at": export["created_at"],
        "updated_at": export["updated_at"]
    })


# Canonical route for listing exports (also accessible via /api/reports/versions/{version_id}/exports)
@router.get("/by-version/{version_id}")
async def list_exports_by_version(
    version_id: str = Path(...),
    status: Optional[str] = Query(None, description="Filter by status")
):
    """List exports for a report version.
    
    - **version_id**: Report version ID
    - **status**: Optional status filter (draft, rendering, ready, delivered, failed)
    """
    db = get_db()
    
    exports = await list_exports(db, version_id, status)
    
    # Format response
    result = []
    for e in exports:
        result.append({
            "id": e["_id"],
            "report_version_id": e["report_version_id"],
            "export_type": e["export_type"],
            "template_version": e["template_version"],
            "status": e["status"],
            "idempotency_key": e.get("idempotency_key"),
            "created_at": e["created_at"],
            "updated_at": e["updated_at"]
        })
    
    return JSONResponse(content={
        "report_version_id": version_id,
        "exports": result
    })
