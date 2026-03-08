"""Report API endpoints."""

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from app.db import get_db
from app.models.report import (
    ReportCreate,
    Report,
    ReportWithPermit,
    ReportVersionCreate,
    ReportVersion,
    StageAttemptsResponse,
    StageAttempt
)
from app.services.report_service import (
    create_report,
    create_report_version,
    get_report,
    get_report_version,
    get_stage_attempts,
    transition_report_status,
    transition_report_version_status
)
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


class StatusTransition(BaseModel):
    status: str
    reason: Optional[str] = ""


@router.post("")
async def create_report_endpoint(request: ReportCreate):
    """Create a new report (draft) for a permit.
    
    - **permit_id**: ID of the permit to create a report for
    """
    db = get_db()
    try:
        report = await create_report(db, request.permit_id)
        model = Report(**report)
        return JSONResponse(content=json.loads(model.model_dump_json(by_alias=False)))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{report_id}")
async def get_report_endpoint(report_id: str = Path(...)):
    """Get a report by ID with denormalized permit data."""
    db = get_db()
    report = await get_report(db, report_id, include_permit=True)
    
    if not report:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    
    model = ReportWithPermit(**report)
    return JSONResponse(content=json.loads(model.model_dump_json(by_alias=False)))


@router.post("/{report_id}/versions")
async def create_report_version_endpoint(
    report_id: str = Path(...),
    request: ReportVersionCreate = ReportVersionCreate()
):
    """Create a new immutable report version with snapshot.
    
    This atomically:
    1. Creates a new report_version with incremented version number
    2. Captures an immutable snapshot of the permit and run config
    3. Updates reports.active_version_id to point to the new version
    
    - **report_id**: ID of the report
    - **snapshot_override**: Optional override fields for the snapshot
    """
    db = get_db()
    try:
        version = await create_report_version(db, report_id, request.snapshot_override)
        model = ReportVersion(**version)
        return JSONResponse(content=json.loads(model.model_dump_json(by_alias=False)))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/versions/{version_id}")
async def get_report_version_endpoint(version_id: str = Path(...)):
    """Get a report version by ID."""
    db = get_db()
    version = await get_report_version(db, version_id)
    
    if not version:
        raise HTTPException(status_code=404, detail=f"Report version {version_id} not found")
    
    model = ReportVersion(**version)
    return JSONResponse(content=json.loads(model.model_dump_json(by_alias=False)))


@router.get("/versions/{version_id}/stage_attempts")
async def get_stage_attempts_endpoint(version_id: str = Path(...)):
    """Get all stage attempts for a report version.
    
    Returns an empty list if no stages have been run yet (Milestone 1).
    """
    db = get_db()
    attempts = await get_stage_attempts(db, version_id)
    
    # Convert to models
    attempt_models = [StageAttempt(**a) for a in attempts]
    response = StageAttemptsResponse(
        report_version_id=version_id,
        stage_attempts=attempt_models
    )
    
    return JSONResponse(content=json.loads(response.model_dump_json(by_alias=False)))



@router.post("/{report_id}/status")
async def transition_report_status_endpoint(
    report_id: str = Path(...),
    request: StatusTransition = ...
):
    """Transition report to a new status.
    
    Validates the transition using the state machine and emits a status_changed event.
    
    - **report_id**: ID of the report
    - **status**: Target status (draft|queued|running|partial|completed|failed|superseded|archived)
    - **reason**: Optional reason for the transition
    
    Returns 400 with INVALID_TRANSITION error if transition is not allowed.
    """
    db = get_db()
    try:
        report = await transition_report_status(db, report_id, request.status, request.reason or "")
        model = Report(**report)
        return JSONResponse(content=json.loads(model.model_dump_json(by_alias=False)))
    except ValueError as e:
        error_msg = str(e)
        if "INVALID_TRANSITION" in error_msg:
            reason = error_msg.replace("INVALID_TRANSITION: ", "")
            report = await db.reports.find_one({"_id": report_id})
            from_status = report["status"] if report else "unknown"
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_TRANSITION",
                    "from": from_status,
                    "to": request.status,
                    "reason": reason
                }
            )
        elif "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=500, detail=error_msg)


@router.post("/versions/{version_id}/status")
async def transition_report_version_status_endpoint(
    version_id: str = Path(...),
    request: StatusTransition = ...
):
    """Transition report version to a new status.
    
    Validates the transition using the state machine and emits a status_changed event.
    
    - **version_id**: ID of the report version
    - **status**: Target status (queued|running|partial|completed|failed)
    - **reason**: Optional reason for the transition
    
    Returns 400 with INVALID_TRANSITION error if transition is not allowed.
    """
    db = get_db()
    try:
        version = await transition_report_version_status(db, version_id, request.status, request.reason or "")
        model = ReportVersion(**version)
        return JSONResponse(content=json.loads(model.model_dump_json(by_alias=False)))
    except ValueError as e:
        error_msg = str(e)
        if "INVALID_TRANSITION" in error_msg:
            reason = error_msg.replace("INVALID_TRANSITION: ", "")
            version = await db.report_versions.find_one({"_id": version_id})
            from_status = version["status"] if version else "unknown"
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_TRANSITION",
                    "from": from_status,
                    "to": request.status,
                    "reason": reason
                }
            )
        elif "not found" in error_msg:
            raise HTTPException(status_code=404, detail=error_msg)
        else:
            raise HTTPException(status_code=500, detail=error_msg)
