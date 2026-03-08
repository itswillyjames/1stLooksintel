"""MongoDB collection definitions and index creation.

All 23 collections are defined here with their indexes.
This ensures the schema is created upfront to avoid disruptive migrations later.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

# Collection names (all 23)
COLLECTIONS = [
    "permits",
    "permit_sources",
    "permit_events",
    "reports",
    "report_versions",
    "report_events",
    "stage_attempts",
    "stage_outputs",
    "stage_events",
    "evidence_items",
    "evidence_links",
    "derived_claims",
    "entities",
    "entity_aliases",
    "entity_identifiers",
    "entity_links",
    "merge_ledger",
    "unmerge_ledger",
    "operator_locks",
    "exports",
    "export_events",
    "report_outcomes",
    "comparables",
]


async def create_indexes(db: AsyncIOMotorDatabase):
    """Create all indexes for all collections.
    
    This is idempotent - MongoDB will skip existing indexes.
    """
    logger.info("Creating indexes for all collections...")
    
    # 1. permits
    await db.permits.create_index([("city", 1), ("filed_date", -1)])
    await db.permits.create_index([("status", 1), ("prequal_score", -1)])
    await db.permits.create_index([("address_norm", 1)])
    await db.permits.create_index([("city", 1), ("source_permit_id", 1)], unique=True)
    
    # 2. permit_sources
    await db.permit_sources.create_index([("permit_id", 1)])
    await db.permit_sources.create_index([("hash", 1)])  # Added per requirements
    
    # 3. permit_events
    await db.permit_events.create_index([("permit_id", 1), ("created_at", -1)])
    
    # 4. reports
    await db.reports.create_index([("permit_id", 1)])
    await db.reports.create_index([("status", 1), ("updated_at", -1)])
    
    # 5. report_versions
    await db.report_versions.create_index([("report_id", 1), ("version", 1)], unique=True)
    await db.report_versions.create_index([("status", 1), ("updated_at", -1)])  # Added per requirements
    
    # 6. report_events
    await db.report_events.create_index([("report_version_id", 1), ("created_at", -1)])
    
    # 7. stage_attempts
    await db.stage_attempts.create_index([("report_version_id", 1), ("stage_name", 1)])
    await db.stage_attempts.create_index([("status", 1)])
    await db.stage_attempts.create_index(
        [("report_version_id", 1), ("stage_name", 1), ("idempotency_key", 1)],
        unique=True
    )
    await db.stage_attempts.create_index(
        [("report_version_id", 1), ("stage_name", 1), ("created_at", -1)]
    )  # Added per requirements
    
    # 8. stage_outputs
    await db.stage_outputs.create_index([("stage_attempt_id", 1)])
    
    # 9. stage_events
    await db.stage_events.create_index([("stage_attempt_id", 1), ("created_at", -1)])
    
    # 10. evidence_items
    await db.evidence_items.create_index([("hash", 1)])
    
    # 11. evidence_links
    await db.evidence_links.create_index([("link_type", 1), ("link_id", 1)])
    await db.evidence_links.create_index([("evidence_id", 1)])
    
    # 12. derived_claims
    await db.derived_claims.create_index([("report_version_id", 1)])
    
    # 13. entities
    await db.entities.create_index([("canonical_name", 1)])
    
    # 14. entity_aliases
    await db.entity_aliases.create_index([("entity_id", 1)])
    await db.entity_aliases.create_index([("alias_norm", 1)])
    
    # 15. entity_identifiers
    await db.entity_identifiers.create_index([("entity_id", 1)])
    await db.entity_identifiers.create_index([("id_type", 1), ("id_value", 1)], unique=True)
    
    # 16. entity_links
    await db.entity_links.create_index([("from_entity_id", 1)])
    await db.entity_links.create_index([("to_entity_id", 1)])
    
    # 17. merge_ledger
    await db.merge_ledger.create_index([("winner_entity_id", 1)])
    await db.merge_ledger.create_index([("merged_entity_id", 1)])
    
    # 18. unmerge_ledger
    await db.unmerge_ledger.create_index([("merge_ledger_id", 1)])
    
    # 19. operator_locks
    await db.operator_locks.create_index([("lock_type", 1), ("lock_id", 1)], unique=True)
    
    # 20. exports
    await db.exports.create_index([("report_version_id", 1), ("status", 1)])
    await db.exports.create_index(
        [("report_version_id", 1), ("export_type", 1), ("template_version", 1)],
        unique=True
    )  # Added per requirements
    
    # 21. export_events
    await db.export_events.create_index([("export_id", 1), ("created_at", -1)])
    
    # 22. report_outcomes
    await db.report_outcomes.create_index([("report_id", 1)])
    
    # 23. comparables
    await db.comparables.create_index([("report_version_id", 1)])
    
    logger.info("All indexes created successfully")
