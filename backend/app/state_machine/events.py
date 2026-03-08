"""Event emission helpers for state transitions.

All events are append-only and immutable.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime, timezone
from typing import Dict, Any
import uuid
import logging

logger = logging.getLogger(__name__)


async def emit_event(
    db: AsyncIOMotorDatabase,
    collection_name: str,
    entity_id_field: str,
    entity_id: str,
    event_type: str,
    event_payload: Dict[str, Any]
) -> str:
    """Emit an event to the appropriate events collection.
    
    Args:
        db: MongoDB database
        collection_name: Name of events collection (e.g., 'permit_events')
        entity_id_field: Name of the entity ID field (e.g., 'permit_id')
        entity_id: ID of the entity
        event_type: Type of event (e.g., 'status_changed')
        event_payload: Event data
    
    Returns:
        Event ID
    
    IMMUTABILITY: Events are append-only. No updates or deletes allowed.
    """
    now = datetime.now(timezone.utc).isoformat()
    
    event_doc = {
        "_id": str(uuid.uuid4()),
        entity_id_field: entity_id,
        "event_type": event_type,
        "event_payload": event_payload,
        "created_at": now,
    }
    
    await db[collection_name].insert_one(event_doc)
    logger.info(f"Emitted {event_type} event for {entity_id_field}={entity_id}")
    
    return event_doc["_id"]


async def emit_status_change_event(
    db: AsyncIOMotorDatabase,
    collection_name: str,
    entity_id_field: str,
    entity_id: str,
    from_status: str,
    to_status: str,
    reason: str = ""
) -> str:
    """Convenience method for status change events."""
    return await emit_event(
        db=db,
        collection_name=collection_name,
        entity_id_field=entity_id_field,
        entity_id=entity_id,
        event_type="status_changed",
        event_payload={
            "from_status": from_status,
            "to_status": to_status,
            "reason": reason
        }
    )
