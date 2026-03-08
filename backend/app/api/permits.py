"""Permit API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import JSONResponse
from typing import Optional
from pydantic import BaseModel
from app.db import get_db
from app.models.permit import (
    PermitListResponse,
    PermitSeedRequest,
    PermitSeedResponse,
    Permit
)
from app.services.permit_service import get_permits, transition_permit_status
from app.db.seed import seed_permits
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/permits", tags=["permits"])


class PermitStatusTransition(BaseModel):
    status: str
    reason: Optional[str] = ""


@router.get("")
async def list_permits(
    city: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0)
):
    """Get permits with optional filters.
    
    - **city**: Filter by city name
    - **status**: Filter by status (new|normalized|prequalified|shortlisted|rejected|archived)
    - **min_score**: Filter by minimum prequalification score
    - **limit**: Number of results (max 100)
    - **skip**: Pagination offset
    """
    db = get_db()
    permits, total = await get_permits(db, city, status, min_score, limit, skip)
    
    # Convert to response models and serialize with by_alias=False (use field name 'id', not '_id')
    permit_models = [Permit(**p) for p in permits]
    response = PermitListResponse(permits=permit_models, total=total)
    
    # Serialize manually to use field names instead of aliases
    return JSONResponse(
        content=json.loads(response.model_dump_json(by_alias=False))
    )


@router.post("/seed", response_model=PermitSeedResponse)
async def seed_permits_endpoint(request: PermitSeedRequest):
    """Seed the database with golden record fixtures.
    
    - **force**: If true, delete existing permits and reseed (default: false)
    
    This is idempotent - running multiple times without force=true will not create duplicates.
    """
    db = get_db()
    result = await seed_permits(db, force=request.force)
    
    return PermitSeedResponse(
        message=result["message"],
        permits_created=result["permits_created"],
        already_existed=result["already_existed"]
    )


@router.post("/{permit_id}/status")
async def transition_permit_status_endpoint(
    permit_id: str = Path(...),
    request: PermitStatusTransition = ...
):
    """Transition permit to a new status.
    
    Validates the transition using the state machine and emits a status_changed event.
    
    - **permit_id**: ID of the permit
    - **status**: Target status (new|normalized|prequalified|shortlisted|rejected|archived)
    - **reason**: Optional reason for the transition
    
    Returns 400 with INVALID_TRANSITION error if transition is not allowed.
    """
    db = get_db()
    try:
        permit = await transition_permit_status(db, permit_id, request.status, request.reason or "")
        model = Permit(**permit)
        return JSONResponse(content=json.loads(model.model_dump_json(by_alias=False)))
    except ValueError as e:
        error_msg = str(e)
        if "INVALID_TRANSITION" in error_msg:
            # Extract the reason from the error message
            reason = error_msg.replace("INVALID_TRANSITION: ", "")
            # Get current permit to extract from_status
            permit = await db.permits.find_one({"_id": permit_id})
            from_status = permit["status"] if permit else "unknown"
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
