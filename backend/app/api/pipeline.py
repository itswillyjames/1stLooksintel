"""Pipeline API endpoints."""

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.db import get_db
from app.pipeline import run_stage
from app.pipeline.stages import ScopeSummaryStage
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


class RunStageRequest(BaseModel):
    idempotency_key: Optional[str] = None


class StageAttemptResponse(BaseModel):
    attempt: Dict[str, Any]
    output: Optional[Dict[str, Any]] = None
    is_rerun: bool = False
    error: Optional[Dict[str, str]] = None


@router.post("/report_versions/{version_id}/stages/scope_summary/run")
async def run_scope_summary_stage(
    version_id: str = Path(...),
    request: RunStageRequest = RunStageRequest()
):
    """Run the scope_summary stage for a report version.
    
    This stage analyzes permit data and generates:
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
async def get_stage_attempt(
    attempt_id: str = Path(...)
):
    """Get a stage attempt by ID, including its output.
    
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
