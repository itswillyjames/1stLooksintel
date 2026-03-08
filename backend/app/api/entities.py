"""Entity resolution API endpoints."""

from fastapi import APIRouter, HTTPException, Path, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from app.db import get_db
from app.entities import (
    extract_entities_from_report_version,
    merge_entities,
    unmerge_entities
)
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/entities", tags=["entities"])


class ExtractEntitiesResponse(BaseModel):
    created_entities: List[str]
    created_aliases: List[str]
    suggestions_created: List[str]
    skipped_locked: List[str]


class MergeRequest(BaseModel):
    winner_entity_id: str
    merged_entity_id: str
    rule: str
    confidence: float = Field(ge=0.0, le=1.0)
    operator_decision: str = "approved"


class UnmergeRequest(BaseModel):
    merge_ledger_id: str
    operator_note: Optional[str] = ""


@router.post("/merge")
async def merge_entities_endpoint(request: MergeRequest):
    """Merge two entities.
    
    Merges merged_entity into winner_entity:
    - Updates merged entity status to 'merged'
    - Re-points all aliases, identifiers, and links to winner
    - Creates merge_ledger entry with diff for unmerge
    
    Requires both entities to be unlocked.
    
    - **winner_entity_id**: Entity to keep
    - **merged_entity_id**: Entity to merge into winner
    - **rule**: Merge rule description (e.g., "exact_match", "operator_manual")
    - **confidence**: Confidence score (0.0-1.0)
    - **operator_decision**: 'approved' or 'rejected' (default: 'approved')
    """
    db = get_db()
    
    try:
        merge_ledger_entry = await merge_entities(
            db=db,
            winner_entity_id=request.winner_entity_id,
            merged_entity_id=request.merged_entity_id,
            rule=request.rule,
            confidence=request.confidence,
            operator_decision=request.operator_decision
        )
        
        return JSONResponse(content={
            "merge_ledger_id": merge_ledger_entry["_id"],
            "winner_entity_id": merge_ledger_entry["winner_entity_id"],
            "merged_entity_id": merge_ledger_entry["merged_entity_id"],
            "rule": merge_ledger_entry["rule"],
            "confidence": merge_ledger_entry["confidence"],
            "created_at": merge_ledger_entry["created_at"]
        })
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error merging entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/unmerge")
async def unmerge_entities_endpoint(request: UnmergeRequest):
    """Unmerge entities using stored diff.
    
    Restores the previous state before merge:
    - Restores merged entity status
    - Restores alias, identifier, and link ownership
    - Creates unmerge_ledger entry for audit trail
    
    - **merge_ledger_id**: ID of merge to reverse
    - **operator_note**: Optional note for audit trail
    """
    db = get_db()
    
    try:
        unmerge_ledger_entry = await unmerge_entities(
            db=db,
            merge_ledger_id=request.merge_ledger_id,
            operator_note=request.operator_note or ""
        )
        
        return JSONResponse(content={
            "unmerge_ledger_id": unmerge_ledger_entry["_id"],
            "merge_ledger_id": unmerge_ledger_entry["merge_ledger_id"],
            "operator_note": unmerge_ledger_entry["operator_note"],
            "created_at": unmerge_ledger_entry["created_at"]
        })
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error unmerging entities: {e}")
        raise HTTPException(status_code=500, detail=str(e))
