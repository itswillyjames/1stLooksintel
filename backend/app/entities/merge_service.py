"""Entity merge and unmerge services with ledger tracking.

IMMUTABILITY:
- merge_ledger is append-only
- unmerge_ledger is append-only
- Aliases are never deleted, only re-pointed
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict, Any, List
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


async def is_entity_locked(db: AsyncIOMotorDatabase, entity_id: str) -> bool:
    """Check if entity is operator-locked."""
    lock = await db.operator_locks.find_one({
        "lock_type": "entity",
        "lock_id": entity_id
    })
    return lock is not None


async def merge_entities(
    db: AsyncIOMotorDatabase,
    winner_entity_id: str,
    merged_entity_id: str,
    rule: str,
    confidence: float,
    operator_decision: str = "approved"
) -> Dict[str, Any]:
    """Merge two entities.
    
    Process:
    1. Verify entities exist and are not locked
    2. Capture current state (diff)
    3. Update merged entity status to 'merged'
    4. Re-point all aliases from merged -> winner
    5. Re-point all identifiers from merged -> winner
    6. Re-point all links from merged -> winner
    7. Create merge_ledger entry with diff
    
    Args:
        db: MongoDB database
        winner_entity_id: Entity to keep
        merged_entity_id: Entity to merge into winner
        rule: Merge rule description
        confidence: Confidence score (0.0-1.0)
        operator_decision: 'approved' or 'rejected'
    
    Returns:
        merge_ledger entry
    
    Raises:
        ValueError: If entities not found, locked, or same
    """
    if winner_entity_id == merged_entity_id:
        raise ValueError("Cannot merge entity with itself")
    
    # Get entities
    winner = await db.entities.find_one({"_id": winner_entity_id})
    merged = await db.entities.find_one({"_id": merged_entity_id})
    
    if not winner:
        raise ValueError(f"Winner entity {winner_entity_id} not found")
    if not merged:
        raise ValueError(f"Merged entity {merged_entity_id} not found")
    
    # Check locks
    if await is_entity_locked(db, winner_entity_id):
        raise ValueError(f"Winner entity {winner_entity_id} is locked")
    if await is_entity_locked(db, merged_entity_id):
        raise ValueError(f"Merged entity {merged_entity_id} is locked")
    
    # Check both are active
    if merged["status"] != "active":
        raise ValueError(f"Merged entity {merged_entity_id} is not active (status: {merged['status']})")
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Capture state before merge (for unmerge)
    # Get aliases
    merged_aliases = await db.entity_aliases.find({"entity_id": merged_entity_id}).to_list(length=1000)
    merged_alias_ids = [a["_id"] for a in merged_aliases]
    
    # Get identifiers
    merged_identifiers = await db.entity_identifiers.find({"entity_id": merged_entity_id}).to_list(length=1000)
    merged_identifier_ids = [i["_id"] for i in merged_identifiers]
    
    # Get links (from_entity or to_entity)
    merged_links_from = await db.entity_links.find({"from_entity_id": merged_entity_id}).to_list(length=1000)
    merged_links_to = await db.entity_links.find({"to_entity_id": merged_entity_id}).to_list(length=1000)
    merged_link_from_ids = [l["_id"] for l in merged_links_from]
    merged_link_to_ids = [l["_id"] for l in merged_links_to]
    
    # Build diff (enough to reverse the merge)
    diff = {
        "merged_entity_id": merged_entity_id,
        "merged_entity_previous_status": merged["status"],
        "merged_alias_ids": merged_alias_ids,
        "merged_identifier_ids": merged_identifier_ids,
        "merged_link_from_ids": merged_link_from_ids,
        "merged_link_to_ids": merged_link_to_ids
    }
    
    # Create merge_ledger entry
    merge_ledger_id = str(uuid.uuid4())
    merge_ledger_doc = {
        "_id": merge_ledger_id,
        "winner_entity_id": winner_entity_id,
        "merged_entity_id": merged_entity_id,
        "rule": rule,
        "confidence": confidence,
        "operator_decision": operator_decision,
        "diff": diff,
        "created_at": now
    }
    
    await db.merge_ledger.insert_one(merge_ledger_doc)
    logger.info(f"Created merge ledger: {merge_ledger_id} ({merged_entity_id} -> {winner_entity_id})")
    
    # Execute merge
    # 1. Update merged entity status
    await db.entities.update_one(
        {"_id": merged_entity_id},
        {"$set": {"status": "merged", "updated_at": now}}
    )
    
    # 2. Re-point aliases
    if merged_alias_ids:
        await db.entity_aliases.update_many(
            {"_id": {"$in": merged_alias_ids}},
            {"$set": {"entity_id": winner_entity_id}}
        )
        logger.info(f"Re-pointed {len(merged_alias_ids)} aliases to winner")
    
    # 3. Re-point identifiers
    if merged_identifier_ids:
        await db.entity_identifiers.update_many(
            {"_id": {"$in": merged_identifier_ids}},
            {"$set": {"entity_id": winner_entity_id}}
        )
        logger.info(f"Re-pointed {len(merged_identifier_ids)} identifiers to winner")
    
    # 4. Re-point links (from_entity)
    if merged_link_from_ids:
        await db.entity_links.update_many(
            {"_id": {"$in": merged_link_from_ids}},
            {"$set": {"from_entity_id": winner_entity_id}}
        )
        logger.info(f"Re-pointed {len(merged_link_from_ids)} from-links to winner")
    
    # 5. Re-point links (to_entity)
    if merged_link_to_ids:
        await db.entity_links.update_many(
            {"_id": {"$in": merged_link_to_ids}},
            {"$set": {"to_entity_id": winner_entity_id}}
        )
        logger.info(f"Re-pointed {len(merged_link_to_ids)} to-links to winner")
    
    logger.info(f"Merge complete: {merged_entity_id} -> {winner_entity_id}")
    
    return merge_ledger_doc


async def unmerge_entities(
    db: AsyncIOMotorDatabase,
    merge_ledger_id: str,
    operator_note: str = ""
) -> Dict[str, Any]:
    """Unmerge entities using stored diff.
    
    Process:
    1. Get merge_ledger entry
    2. Verify merged entity still exists
    3. Restore entity status
    4. Restore alias ownership (from diff)
    5. Restore identifier ownership (from diff)
    6. Restore link ownership (from diff)
    7. Create unmerge_ledger entry
    
    Args:
        db: MongoDB database
        merge_ledger_id: ID of merge to reverse
        operator_note: Optional note for audit trail
    
    Returns:
        unmerge_ledger entry
    
    Raises:
        ValueError: If merge_ledger not found
    """
    # Get merge ledger entry
    merge_entry = await db.merge_ledger.find_one({"_id": merge_ledger_id})
    if not merge_entry:
        raise ValueError(f"Merge ledger entry {merge_ledger_id} not found")
    
    diff = merge_entry["diff"]
    merged_entity_id = diff["merged_entity_id"]
    merged_alias_ids = diff["merged_alias_ids"]
    merged_identifier_ids = diff["merged_identifier_ids"]
    merged_link_from_ids = diff["merged_link_from_ids"]
    merged_link_to_ids = diff["merged_link_to_ids"]
    previous_status = diff["merged_entity_previous_status"]
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Verify merged entity exists
    merged_entity = await db.entities.find_one({"_id": merged_entity_id})
    if not merged_entity:
        raise ValueError(f"Merged entity {merged_entity_id} not found (cannot unmerge)")
    
    # Create unmerge_ledger entry
    unmerge_ledger_id = str(uuid.uuid4())
    unmerge_ledger_doc = {
        "_id": unmerge_ledger_id,
        "merge_ledger_id": merge_ledger_id,
        "operator_note": operator_note,
        "diff": diff,  # Store same diff for audit
        "created_at": now
    }
    
    await db.unmerge_ledger.insert_one(unmerge_ledger_doc)
    logger.info(f"Created unmerge ledger: {unmerge_ledger_id}")
    
    # Execute unmerge
    # 1. Restore entity status
    await db.entities.update_one(
        {"_id": merged_entity_id},
        {"$set": {"status": previous_status, "updated_at": now}}
    )
    logger.info(f"Restored entity {merged_entity_id} status to {previous_status}")
    
    # 2. Restore alias ownership
    if merged_alias_ids:
        await db.entity_aliases.update_many(
            {"_id": {"$in": merged_alias_ids}},
            {"$set": {"entity_id": merged_entity_id}}
        )
        logger.info(f"Restored {len(merged_alias_ids)} aliases to merged entity")
    
    # 3. Restore identifier ownership
    if merged_identifier_ids:
        await db.entity_identifiers.update_many(
            {"_id": {"$in": merged_identifier_ids}},
            {"$set": {"entity_id": merged_entity_id}}
        )
        logger.info(f"Restored {len(merged_identifier_ids)} identifiers to merged entity")
    
    # 4. Restore link ownership (from_entity)
    if merged_link_from_ids:
        await db.entity_links.update_many(
            {"_id": {"$in": merged_link_from_ids}},
            {"$set": {"from_entity_id": merged_entity_id}}
        )
        logger.info(f"Restored {len(merged_link_from_ids)} from-links to merged entity")
    
    # 5. Restore link ownership (to_entity)
    if merged_link_to_ids:
        await db.entity_links.update_many(
            {"_id": {"$in": merged_link_to_ids}},
            {"$set": {"to_entity_id": merged_entity_id}}
        )
        logger.info(f"Restored {len(merged_link_to_ids)} to-links to merged entity")
    
    logger.info(f"Unmerge complete: restored {merged_entity_id}")
    
    return unmerge_ledger_doc
