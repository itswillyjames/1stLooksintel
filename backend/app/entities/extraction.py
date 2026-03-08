"""Entity extraction from permits and stage outputs.

Deterministic extraction (no external OSINT yet).
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict, Any, List, Set
from datetime import datetime, timezone
import uuid
import logging

from app.entities.canonicalization import normalize_name, exact_match, fuzzy_match

logger = logging.getLogger(__name__)


async def is_entity_locked(db: AsyncIOMotorDatabase, entity_id: str) -> bool:
    """Check if entity is operator-locked."""
    lock = await db.operator_locks.find_one({
        "lock_type": "entity",
        "lock_id": entity_id
    })
    return lock is not None


async def find_entity_by_alias_norm(
    db: AsyncIOMotorDatabase,
    alias_norm: str,
    entity_type: str
) -> List[Dict[str, Any]]:
    """Find entities with matching alias_norm."""
    # Find aliases with this norm
    aliases = await db.entity_aliases.find({
        "alias_norm": alias_norm
    }).to_list(length=100)
    
    if not aliases:
        return []
    
    # Get unique entity IDs
    entity_ids = list(set(a["entity_id"] for a in aliases))
    
    # Get entities
    entities = await db.entities.find({
        "_id": {"$in": entity_ids},
        "entity_type": entity_type,
        "status": "active"  # Only active entities
    }).to_list(length=100)
    
    return entities


async def create_entity(
    db: AsyncIOMotorDatabase,
    entity_type: str,
    canonical_name: str,
    city: str = None
) -> str:
    """Create a new entity."""
    now = datetime.now(timezone.utc).isoformat()
    entity_id = str(uuid.uuid4())
    
    entity_doc = {
        "_id": entity_id,
        "entity_type": entity_type,
        "canonical_name": canonical_name,
        "city": city,
        "status": "active",
        "created_at": now,
        "updated_at": now
    }
    
    await db.entities.insert_one(entity_doc)
    logger.info(f"Created entity: {entity_id} ({canonical_name})")
    
    return entity_id


async def create_alias(
    db: AsyncIOMotorDatabase,
    entity_id: str,
    alias: str,
    alias_norm: str,
    source_evidence_id: str = None
) -> str:
    """Create an entity alias."""
    now = datetime.now(timezone.utc).isoformat()
    alias_id = str(uuid.uuid4())
    
    alias_doc = {
        "_id": alias_id,
        "entity_id": entity_id,
        "alias": alias,
        "alias_norm": alias_norm,
        "source_evidence_id": source_evidence_id,
        "address_norm": None,
        "phone": None,
        "email": None,
        "website": None,
        "created_at": now
    }
    
    await db.entity_aliases.insert_one(alias_doc)
    return alias_id


async def create_suggestion(
    db: AsyncIOMotorDatabase,
    report_version_id: str,
    observed_name: str,
    observed_role: str,
    observed_source: str,
    alias_norm: str,
    candidate_entity_ids: List[str],
    match_type: str,
    confidence: float
) -> str:
    """Create an entity match suggestion."""
    now = datetime.now(timezone.utc).isoformat()
    suggestion_id = str(uuid.uuid4())
    
    suggestion_doc = {
        "_id": suggestion_id,
        "report_version_id": report_version_id,
        "observed_name": observed_name,
        "observed_role": observed_role,
        "observed_source": observed_source,
        "alias_norm": alias_norm,
        "candidate_entity_ids": candidate_entity_ids,
        "match_type": match_type,
        "confidence": confidence,
        "status": "open",
        "created_at": now,
        "updated_at": now
    }
    
    await db.entity_match_suggestions.insert_one(suggestion_doc)
    return suggestion_id


async def extract_entities_from_report_version(
    db: AsyncIOMotorDatabase,
    report_version_id: str
) -> Dict[str, Any]:
    """Extract entities from report version (permit + stage outputs).
    
    Sources:
    1. Permit snapshot: owner_raw, contractor_raw, applicant_raw
    2. Stage outputs: scope_summary (future: other stages)
    
    Returns:
        {
            "created_entities": [entity_ids],
            "created_aliases": [alias_ids],
            "suggestions_created": [suggestion_ids],
            "skipped_locked": [entity_names]
        }
    """
    # Get report version
    version = await db.report_versions.find_one({"_id": report_version_id})
    if not version:
        raise ValueError(f"Report version {report_version_id} not found")
    
    snapshot = version.get("snapshot", {})
    permit = snapshot.get("permit", {})
    city = permit.get("city", "")
    
    created_entities = []
    created_aliases = []
    suggestions_created = []
    skipped_locked = []
    
    # Extract from permit fields
    permit_entities = []
    
    if permit.get("owner_raw"):
        permit_entities.append({
            "name": permit["owner_raw"],
            "role": "owner",
            "source": "permit",
            "type": "org"  # Assume org for now
        })
    
    if permit.get("contractor_raw"):
        permit_entities.append({
            "name": permit["contractor_raw"],
            "role": "contractor",
            "source": "permit",
            "type": "org"
        })
    
    if permit.get("applicant_raw"):
        permit_entities.append({
            "name": permit["applicant_raw"],
            "role": "applicant",
            "source": "permit",
            "type": "org"
        })
    
    # Process each observed entity
    processed_norms: Set[str] = set()
    
    for entity_obs in permit_entities:
        name = entity_obs["name"]
        role = entity_obs["role"]
        source = entity_obs["source"]
        entity_type = entity_obs["type"]
        
        alias_norm = normalize_name(name)
        
        # Skip if already processed this normalized name
        if alias_norm in processed_norms:
            continue
        processed_norms.add(alias_norm)
        
        # Skip empty names
        if not alias_norm:
            continue
        
        # Find exact matches
        exact_matches = await find_entity_by_alias_norm(db, alias_norm, entity_type)
        
        if exact_matches:
            # Exact match found
            # Check if locked
            locked = False
            for match in exact_matches:
                if await is_entity_locked(db, match["_id"]):
                    locked = True
                    skipped_locked.append(name)
                    break
            
            if not locked and len(exact_matches) == 1:
                # Single exact match, not locked - create alias for existing entity
                entity_id = exact_matches[0]["_id"]
                
                # Check if alias already exists
                existing_alias = await db.entity_aliases.find_one({
                    "entity_id": entity_id,
                    "alias_norm": alias_norm
                })
                
                if not existing_alias:
                    alias_id = await create_alias(db, entity_id, name, alias_norm)
                    created_aliases.append(alias_id)
                    logger.info(f"Added alias to existing entity: {name} -> {entity_id}")
            elif not locked and len(exact_matches) > 1:
                # Multiple exact matches - create suggestion for operator review
                candidate_ids = [e["_id"] for e in exact_matches]
                sugg_id = await create_suggestion(
                    db=db,
                    report_version_id=report_version_id,
                    observed_name=name,
                    observed_role=role,
                    observed_source=source,
                    alias_norm=alias_norm,
                    candidate_entity_ids=candidate_ids,
                    match_type="exact",
                    confidence=1.0
                )
                suggestions_created.append(sugg_id)
                logger.info(f"Created suggestion for {name}: {len(exact_matches)} exact matches")
        else:
            # No exact match - check fuzzy matches
            # Get all entities of this type
            all_entities = await db.entities.find({
                "entity_type": entity_type,
                "status": "active"
            }).to_list(length=1000)
            
            fuzzy_candidates = []
            for entity in all_entities:
                # Check against canonical name and all aliases
                is_match, confidence = fuzzy_match(name, entity["canonical_name"], threshold=0.90)
                if is_match:
                    fuzzy_candidates.append((entity["_id"], confidence))
            
            if fuzzy_candidates:
                # Fuzzy matches found - create suggestion (no auto-merge)
                # Sort by confidence
                fuzzy_candidates.sort(key=lambda x: x[1], reverse=True)
                candidate_ids = [c[0] for c in fuzzy_candidates]
                max_confidence = fuzzy_candidates[0][1]
                
                # Check if any are locked
                locked = False
                for cand_id, _ in fuzzy_candidates:
                    if await is_entity_locked(db, cand_id):
                        locked = True
                        skipped_locked.append(name)
                        break
                
                if not locked:
                    sugg_id = await create_suggestion(
                        db=db,
                        report_version_id=report_version_id,
                        observed_name=name,
                        observed_role=role,
                        observed_source=source,
                        alias_norm=alias_norm,
                        candidate_entity_ids=candidate_ids,
                        match_type="fuzzy",
                        confidence=max_confidence
                    )
                    suggestions_created.append(sugg_id)
                    logger.info(f"Created fuzzy suggestion for {name}: {len(fuzzy_candidates)} candidates")
            else:
                # No matches - create new entity
                entity_id = await create_entity(
                    db=db,
                    entity_type=entity_type,
                    canonical_name=name,
                    city=city
                )
                created_entities.append(entity_id)
                
                # Create alias for new entity
                alias_id = await create_alias(db, entity_id, name, alias_norm)
                created_aliases.append(alias_id)
                
                logger.info(f"Created new entity: {name} ({entity_id})")
    
    return {
        "created_entities": created_entities,
        "created_aliases": created_aliases,
        "suggestions_created": suggestions_created,
        "skipped_locked": skipped_locked
    }
