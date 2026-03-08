"""Permit service - business logic for permit operations."""

from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


def compute_prequal_score(permit_data: Dict[str, Any]) -> tuple[float, List[str]]:
    """Deterministic prequalification scoring.
    
    Rules:
    - Base score: 15
    - Valuation >= $750K: +40 points
    - Work type in [commercial, industrial, institutional]: +30 points
    - Keywords (new construction, tenant improvement, expansion): +15 points
    
    Thresholds:
    - Reject (noise): < 50
    - Shortlist: >= 70
    """
    score = 15.0
    reasons = []
    
    # Valuation check
    valuation = permit_data.get("valuation") or 0
    if valuation >= 750000:
        score += 40
        reasons.append(f"High valuation: ${valuation:,}")
    
    # Work type check
    work_type = (permit_data.get("work_type") or "").lower()
    if any(wt in work_type for wt in ["commercial", "industrial", "institutional"]):
        score += 30
        reasons.append(f"Target work type: {work_type}")
    
    # Keyword check
    description = (permit_data.get("description_raw") or "").lower()
    keywords = ["new construction", "tenant improvement", "expansion"]
    matched_keywords = [kw for kw in keywords if kw in description]
    if matched_keywords:
        score += 15
        reasons.append(f"Project keywords: {', '.join(matched_keywords)}")
    
    if not reasons:
        reasons.append("Base score only - low commercial value")
    
    return score, reasons


def normalize_permit(permit_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize permit data and compute prequalification."""
    # Basic normalization
    if permit_data.get("address_raw"):
        # Simple normalization: uppercase, strip
        permit_data["address_norm"] = permit_data["address_raw"].upper().strip()
    
    # Compute prequal score
    score, reasons = compute_prequal_score(permit_data)
    permit_data["prequal_score"] = score
    permit_data["prequal_reasons"] = reasons
    
    # Set status based on score
    if score < 50:
        permit_data["status"] = "rejected"
    elif score >= 70:
        permit_data["status"] = "shortlisted"
    else:
        permit_data["status"] = "prequalified"
    
    return permit_data


async def create_permit(
    db: AsyncIOMotorDatabase,
    permit_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Create a new permit with normalization and prequalification."""
    now = datetime.now(timezone.utc).isoformat()
    
    # Normalize
    permit_data = normalize_permit(permit_data)
    
    # Add metadata
    permit_doc = {
        "_id": str(uuid.uuid4()),
        **permit_data,
        "created_at": now,
        "updated_at": now,
    }
    
    # Insert
    try:
        await db.permits.insert_one(permit_doc)
        logger.info(f"Created permit {permit_doc['_id']} with score {permit_doc['prequal_score']}")
        return permit_doc
    except Exception as e:
        # Handle duplicate key (city + source_permit_id)
        if "duplicate key" in str(e).lower():
            logger.warning(f"Permit already exists: {permit_data['city']}/{permit_data['source_permit_id']}")
            # Return existing permit
            existing = await db.permits.find_one(
                {"city": permit_data["city"], "source_permit_id": permit_data["source_permit_id"]},
                {"_id": 0}
            )
            return existing
        raise


async def get_permits(
    db: AsyncIOMotorDatabase,
    city: Optional[str] = None,
    status: Optional[str] = None,
    min_score: Optional[float] = None,
    limit: int = 50,
    skip: int = 0
) -> tuple[List[Dict[str, Any]], int]:
    """Get permits with filtering."""
    query = {}
    
    if city:
        query["city"] = city
    if status:
        query["status"] = status
    if min_score is not None:
        query["prequal_score"] = {"$gte": min_score}
    
    # Count total
    total = await db.permits.count_documents(query)
    
    # Get paginated results (include _id)
    cursor = db.permits.find(query).sort("prequal_score", -1).skip(skip).limit(limit)
    permits = await cursor.to_list(length=limit)
    
    return permits, total


async def get_permit_by_id(db: AsyncIOMotorDatabase, permit_id: str) -> Optional[Dict[str, Any]]:
    """Get a single permit by ID."""
    permit = await db.permits.find_one({"_id": permit_id})
    return permit
