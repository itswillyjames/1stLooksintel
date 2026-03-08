"""Report API endpoints."""

from fastapi import APIRouter, HTTPException, Path, Query
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
from app.pipeline import run_stage
from app.pipeline.stages import ScopeSummaryStage
from app.entities import extract_entities_from_report_version

import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reports", tags=["reports"])


class StatusTransition(BaseModel):
    status: str
    reason: Optional[str] = ""


class RunStageRequest(BaseModel):
    idempotency_key: Optional[str] = None



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


# ============================================================================
# CANONICAL PIPELINE ROUTES (aliases to /api/pipeline/* for cleaner URLs)
# ============================================================================

@router.post("/versions/{version_id}/stages/scope_summary/run")
async def run_scope_summary_stage_canonical(
    version_id: str = Path(...),
    request: RunStageRequest = RunStageRequest()
):
    """Run the scope_summary stage for a report version (canonical route).
    
    This is an alias to POST /api/pipeline/report_versions/{version_id}/stages/scope_summary/run
    for cleaner URL structure.
    
    Analyzes permit data and generates:
    - Project type classification
    - Human-readable scope summary
    - Estimated project size
    - Buyer fit scoring
    
    Idempotency: Running with the same idempotency_key will return the existing
    attempt/output without re-executing the stage.
    
    - **version_id**: Report version ID
    - **idempotency_key**: Optional custom key for idempotency (auto-generated if not provided)
    """
    db = get_db()
    
    try:
        # Get report version and extract permit data from snapshot
        version = await db.report_versions.find_one({"_id": version_id})
        if not version:
            raise HTTPException(status_code=404, detail=f"Report version {version_id} not found")
        
        # Extract permit from snapshot
        snapshot = version.get("snapshot", {})
        permit_data = snapshot.get("permit", {})
        
        if not permit_data:
            raise HTTPException(
                status_code=400,
                detail="Report version snapshot does not contain permit data"
            )
        
        # Prepare input for stage
        stage_input = {
            "permit_id": permit_data.get("_id", ""),
            "city": permit_data.get("city", ""),
            "address_raw": permit_data.get("address_raw", ""),
            "work_type": permit_data.get("work_type", ""),
            "description_raw": permit_data.get("description_raw", ""),
            "valuation": permit_data.get("valuation", 0),
            "filed_date": permit_data.get("filed_date", ""),
            "issued_date": permit_data.get("issued_date")
        }
        
        # Run stage
        stage_runner = ScopeSummaryStage()
        result = await run_stage(
            db=db,
            stage_runner=stage_runner,
            report_version_id=version_id,
            input_data=stage_input,
            idempotency_key=request.idempotency_key
        )
        
        return JSONResponse(content={
            "attempt": {
                "id": result["attempt"]["_id"],
                **{k: v for k, v in result["attempt"].items() if k != "_id"}
            },
            "output": {
                "id": result["output"]["_id"],
                **{k: v for k, v in result["output"].items() if k != "_id"}
            } if result["output"] else None,
            "is_rerun": result["is_rerun"],
            "error": result.get("error")
        })
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error running scope_summary stage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stage_attempts/{attempt_id}")
async def get_stage_attempt_canonical(
    attempt_id: str = Path(...),
):
    """Get a stage attempt by ID, including its output (canonical route).
    
    This is an alias to GET /api/pipeline/stage_attempts/{attempt_id}
    for cleaner URL structure.
    
    - **attempt_id**: Stage attempt ID
    """
    db = get_db()
    
    # Get attempt
    attempt = await db.stage_attempts.find_one({"_id": attempt_id})
    if not attempt:
        raise HTTPException(status_code=404, detail=f"Stage attempt {attempt_id} not found")
    
    # Get output (if exists)
    output = await db.stage_outputs.find_one({"stage_attempt_id": attempt_id})
    
    return JSONResponse(content={
        "attempt": {
            "id": attempt["_id"],
            **{k: v for k, v in attempt.items() if k != "_id"}
        },
        "output": {
            "id": output["_id"],
            **{k: v for k, v in output.items() if k != "_id"}
        } if output else None
    })


# ============================================================================
# ENTITY RESOLUTION ENDPOINTS
# ============================================================================

@router.post("/versions/{version_id}/entities/extract")
async def extract_entities_endpoint(
    version_id: str = Path(...),
):
    """Extract entities from report version.
    
    Deterministically extracts entities from:
    - Permit snapshot (owner_raw, contractor_raw, applicant_raw)
    - Stage outputs (scope_summary, etc.)
    
    Creates entities, aliases, and match suggestions for operator review.
    
    - **version_id**: Report version ID
    
    Returns:
        {
            "created_entities": [entity_ids],
            "created_aliases": [alias_ids],
            "suggestions_created": [suggestion_ids],
            "skipped_locked": [entity_names]
        }
    """
    db = get_db()
    
    try:
        result = await extract_entities_from_report_version(db, version_id)
        
        return JSONResponse(content=result)
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error extracting entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/versions/{version_id}/entity_suggestions")
async def get_entity_suggestions_endpoint(
    version_id: str = Path(...),
    status: Optional[str] = Query("open")
):
    """Get entity match suggestions for review.
    
    Lists suggestions generated during entity extraction that require
    operator review (exact matches with multiple candidates, fuzzy matches).
    
    - **version_id**: Report version ID
    - **status**: Filter by status (default: 'open')
    
    Returns:
        {
            "suggestions": [
                {
                    "id": "...",
                    "observed_name": "Reliable Builders Inc",
                    "observed_role": "contractor",
                    "candidate_entity_ids": ["...", "..."],
                    "match_type": "exact|fuzzy",
                    "confidence": 0.95,
                    "status": "open"
                }
            ]
        }
    """
    db = get_db()
    
    query = {"report_version_id": version_id}
    if status:
        query["status"] = status
    
    suggestions = await db.entity_match_suggestions.find(query).to_list(length=1000)
    
    # Format response
    result = []
    for s in suggestions:
        result.append({
            "id": s["_id"],
            "observed_name": s["observed_name"],
            "observed_role": s["observed_role"],
            "observed_source": s["observed_source"],
            "alias_norm": s["alias_norm"],
            "candidate_entity_ids": s["candidate_entity_ids"],
            "match_type": s["match_type"],
            "confidence": s["confidence"],
            "status": s["status"],
            "created_at": s["created_at"],
            "updated_at": s["updated_at"]
        })
    
    return JSONResponse(content={"suggestions": result})

