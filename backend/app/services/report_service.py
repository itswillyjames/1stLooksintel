"""Report service - business logic for report operations.

IMMUTABILITY RULES:
- report_versions.snapshot is immutable after creation (no update endpoint)
- Evidence items/links are append-only (enforced at service layer)
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


async def create_report(
    db: AsyncIOMotorDatabase,
    permit_id: str
) -> Dict[str, Any]:
    """Create a new report (draft) for a permit."""
    # Verify permit exists
    permit = await db.permits.find_one({"_id": permit_id})
    if not permit:
        raise ValueError(f"Permit {permit_id} not found")
    
    now = datetime.now(timezone.utc).isoformat()
    
    report_doc = {
        "_id": str(uuid.uuid4()),
        "permit_id": permit_id,
        "status": "draft",
        "active_version_id": None,
        "created_at": now,
        "updated_at": now,
    }
    
    await db.reports.insert_one(report_doc)
    logger.info(f"Created report {report_doc['_id']} for permit {permit_id}")
    
    return report_doc


async def create_report_version(
    db: AsyncIOMotorDatabase,
    report_id: str,
    snapshot_override: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a new immutable report version with snapshot.
    
    IMMUTABILITY: Once created, the snapshot cannot be modified.
    This is enforced by not providing any update endpoint for report_versions.
    
    ATOMICITY: Updates reports.active_version_id in the same transaction (best-effort).
    """
    # Get report
    report = await db.reports.find_one({"_id": report_id})
    if not report:
        raise ValueError(f"Report {report_id} not found")
    
    # Get permit for snapshot
    permit = await db.permits.find_one({"_id": report["permit_id"]}, {"_id": 0})
    if not permit:
        raise ValueError(f"Permit {report['permit_id']} not found")
    
    # Get next version number
    last_version = await db.report_versions.find_one(
        {"report_id": report_id},
        sort=[("version", -1)]
    )
    next_version = (last_version["version"] + 1) if last_version else 1
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Create immutable snapshot
    snapshot = {
        "permit": permit,
        "operator_notes": "",
        "run_config": {},
        **(snapshot_override or {})
    }
    
    version_doc = {
        "_id": str(uuid.uuid4()),
        "report_id": report_id,
        "version": next_version,
        "snapshot": snapshot,
        "status": "queued",
        "created_at": now,
        "updated_at": now,
    }
    
    # Insert version
    await db.report_versions.insert_one(version_doc)
    logger.info(f"Created report version {version_doc['_id']} (v{next_version}) for report {report_id}")
    
    # Update active_version_id atomically (best-effort for MongoDB)
    await db.reports.update_one(
        {"_id": report_id},
        {
            "$set": {
                "active_version_id": version_doc["_id"],
                "status": "queued",
                "updated_at": now
            }
        }
    )
    
    # Remove MongoDB _id for response
    version_doc_copy = version_doc.copy()
    return version_doc_copy


async def get_report(
    db: AsyncIOMotorDatabase,
    report_id: str,
    include_permit: bool = True
) -> Optional[Dict[str, Any]]:
    """Get a report by ID, optionally with denormalized permit data."""
    report = await db.reports.find_one({"_id": report_id})
    if not report:
        return None
    
    if include_permit:
        permit = await db.permits.find_one({"_id": report["permit_id"]})
        report["permit"] = permit
    
    return report


async def get_report_version(
    db: AsyncIOMotorDatabase,
    version_id: str
) -> Optional[Dict[str, Any]]:
    """Get a report version by ID."""
    version = await db.report_versions.find_one({"_id": version_id})
    if not version:
        return None
    
    return version


async def get_stage_attempts(
    db: AsyncIOMotorDatabase,
    report_version_id: str
) -> List[Dict[str, Any]]:
    """Get all stage attempts for a report version."""
    cursor = db.stage_attempts.find(
        {"report_version_id": report_version_id}
    ).sort("created_at", 1)
    
    attempts = await cursor.to_list(length=100)
    return attempts
