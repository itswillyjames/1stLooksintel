"""Permit API endpoints."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
from app.db import get_db
from app.models.permit import (
    PermitListResponse,
    PermitSeedRequest,
    PermitSeedResponse,
    Permit
)
from app.services.permit_service import get_permits
from app.db.seed import seed_permits
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/permits", tags=["permits"])


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
