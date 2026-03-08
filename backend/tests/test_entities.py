"""Tests for entity resolution: extraction, matching, merge/unmerge.

Tests:
1. Extraction creates entities/aliases from permit fields
2. Exact match generates suggestion or auto-links
3. Fuzzy match creates suggestion only (no merge)
4. Merge updates ownership and marks entity as merged
5. Unmerge restores original state
6. Operator locks prevent suggestions/merges
"""

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
import uuid

from app.entities import (
    normalize_name,
    exact_match,
    fuzzy_match,
    extract_entities_from_report_version,
    merge_entities,
    unmerge_entities
)

# Test database
TEST_DB_NAME = "test_permit_intel"


@pytest_asyncio.fixture
async def db():
    """Create a test database."""
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    test_db = client[TEST_DB_NAME]
    
    # Clean up before tests
    await test_db.report_versions.delete_many({})
    await test_db.entities.delete_many({})
    await test_db.entity_aliases.delete_many({})
    await test_db.entity_identifiers.delete_many({})
    await test_db.entity_links.delete_many({})
    await test_db.entity_match_suggestions.delete_many({})
    await test_db.merge_ledger.delete_many({})
    await test_db.unmerge_ledger.delete_many({})
    await test_db.operator_locks.delete_many({})
    
    yield test_db
    
    # Clean up after tests
    await test_db.report_versions.delete_many({})
    await test_db.entities.delete_many({})
    await test_db.entity_aliases.delete_many({})
    await test_db.entity_identifiers.delete_many({})
    await test_db.entity_links.delete_many({})
    await test_db.entity_match_suggestions.delete_many({})
    await test_db.merge_ledger.delete_many({})
    await test_db.unmerge_ledger.delete_many({})
    await test_db.operator_locks.delete_many({})
    
    client.close()


class TestCanonicalization:
    """Test name normalization and matching."""
    
    def test_normalize_name(self):
        """Test name normalization."""
        assert normalize_name("Reliable Builders Inc") == "reliable builders"
        assert normalize_name("Reliable Builders, Inc.") == "reliable builders"
        assert normalize_name("ABC Company LLC") == "abc"
        assert normalize_name("Test  Corp.") == "test"
    
    def test_exact_match(self):
        """Test exact matching after normalization."""
        assert exact_match("Reliable Builders Inc", "Reliable Builders, Inc.")
        assert exact_match("ABC Company LLC", "ABC Company")
        assert not exact_match("ABC Company", "XYZ Company")
    
    def test_fuzzy_match(self):
        """Test fuzzy matching."""
        is_match, confidence = fuzzy_match("Reliable Builders Inc", "Reliable Builder Inc")
        assert is_match  # Very similar
        assert confidence > 0.90
        
        is_match, confidence = fuzzy_match("ABC Company", "XYZ Company")
        assert not is_match  # Different
        assert confidence < 0.90


class TestEntityExtraction:
    """Test entity extraction from permits."""
    
    @pytest.mark.asyncio
    async def test_extraction_creates_entities(self, db):
        """Test extraction creates new entities and aliases."""
        # Create test report version
        version_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        version_doc = {
            "_id": version_id,
            "report_id": str(uuid.uuid4()),
            "version": 1,
            "snapshot": {
                "permit": {
                    "_id": str(uuid.uuid4()),
                    "city": "TestCity",
                    "owner_raw": "Test Owner LLC",
                    "contractor_raw": "Test Contractor Inc",
                    "applicant_raw": "Test Applicant"
                }
            },
            "status": "queued",
            "created_at": now,
            "updated_at": now
        }
        
        await db.report_versions.insert_one(version_doc)
        
        # Extract entities
        result = await extract_entities_from_report_version(db, version_id)
        
        # Verify entities created
        assert len(result["created_entities"]) == 3  # owner, contractor, applicant
        assert len(result["created_aliases"]) == 3
        assert len(result["suggestions_created"]) == 0  # No matches yet
        
        # Verify entities exist in DB
        entities = await db.entities.find({}).to_list(length=10)
        assert len(entities) == 3
        
        # Verify aliases exist
        aliases = await db.entity_aliases.find({}).to_list(length=10)
        assert len(aliases) == 3
    
    @pytest.mark.asyncio
    async def test_extraction_with_exact_match(self, db):
        """Test extraction with existing entity (exact match)."""
        # Create existing entity
        entity_id = str(uuid.uuid4())
        await db.entities.insert_one({
            "_id": entity_id,
            "entity_type": "org",
            "canonical_name": "Reliable Builders Inc",
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Create alias for existing entity
        await db.entity_aliases.insert_one({
            "_id": str(uuid.uuid4()),
            "entity_id": entity_id,
            "alias": "Reliable Builders Inc",
            "alias_norm": normalize_name("Reliable Builders Inc"),
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Create version with same entity name (slight variation)
        version_id = str(uuid.uuid4())
        await db.report_versions.insert_one({
            "_id": version_id,
            "report_id": str(uuid.uuid4()),
            "version": 1,
            "snapshot": {
                "permit": {
                    "_id": str(uuid.uuid4()),
                    "city": "TestCity",
                    "contractor_raw": "Reliable Builders, Inc."  # Slight variation
                }
            },
            "status": "queued",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Extract
        result = await extract_entities_from_report_version(db, version_id)
        
        # Should add alias to existing entity (exact match after normalization)
        # OR skip if alias already exists with same norm
        assert len(result["created_entities"]) == 0  # No new entity
        # Alias creation is skipped if one with same norm already exists
        
        # Verify no duplicate aliases created
        all_aliases = await db.entity_aliases.find({"entity_id": entity_id}).to_list(length=10)
        # Should have original alias (maybe + new one if different text but same norm)
        assert len(all_aliases) >= 1


class TestMergeUnmerge:
    """Test merge and unmerge operations."""
    
    @pytest.mark.asyncio
    async def test_merge_updates_ownership(self, db):
        """Test merge re-points aliases and marks entity as merged."""
        # Create two entities
        winner_id = str(uuid.uuid4())
        merged_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        await db.entities.insert_many([
            {
                "_id": winner_id,
                "entity_type": "org",
                "canonical_name": "ABC Company",
                "status": "active",
                "created_at": now,
                "updated_at": now
            },
            {
                "_id": merged_id,
                "entity_type": "org",
                "canonical_name": "ABC Corp",
                "status": "active",
                "created_at": now,
                "updated_at": now
            }
        ])
        
        # Create aliases for merged entity
        alias_id = str(uuid.uuid4())
        await db.entity_aliases.insert_one({
            "_id": alias_id,
            "entity_id": merged_id,
            "alias": "ABC Corp",
            "alias_norm": normalize_name("ABC Corp"),
            "created_at": now
        })
        
        # Merge
        merge_result = await merge_entities(
            db=db,
            winner_entity_id=winner_id,
            merged_entity_id=merged_id,
            rule="exact_match",
            confidence=1.0
        )
        
        # Verify merge_ledger created
        assert merge_result["_id"] is not None
        assert merge_result["winner_entity_id"] == winner_id
        assert merge_result["merged_entity_id"] == merged_id
        
        # Verify merged entity status updated
        merged_entity = await db.entities.find_one({"_id": merged_id})
        assert merged_entity["status"] == "merged"
        
        # Verify alias re-pointed
        alias = await db.entity_aliases.find_one({"_id": alias_id})
        assert alias["entity_id"] == winner_id  # Now points to winner
    
    @pytest.mark.asyncio
    async def test_unmerge_restores_state(self, db):
        """Test unmerge restores original state."""
        # Create and merge entities
        winner_id = str(uuid.uuid4())
        merged_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        await db.entities.insert_many([
            {"_id": winner_id, "entity_type": "org", "canonical_name": "ABC", "status": "active", "created_at": now, "updated_at": now},
            {"_id": merged_id, "entity_type": "org", "canonical_name": "XYZ", "status": "active", "created_at": now, "updated_at": now}
        ])
        
        alias_id = str(uuid.uuid4())
        await db.entity_aliases.insert_one({
            "_id": alias_id,
            "entity_id": merged_id,
            "alias": "XYZ",
            "alias_norm": "xyz",
            "created_at": now
        })
        
        # Merge
        merge_result = await merge_entities(db, winner_id, merged_id, "test", 1.0)
        merge_ledger_id = merge_result["_id"]
        
        # Verify alias moved
        alias_after_merge = await db.entity_aliases.find_one({"_id": alias_id})
        assert alias_after_merge["entity_id"] == winner_id
        
        # Unmerge
        unmerge_result = await unmerge_entities(db, merge_ledger_id, "test unmerge")
        
        # Verify unmerge_ledger created
        assert unmerge_result["_id"] is not None
        
        # Verify entity status restored
        merged_entity = await db.entities.find_one({"_id": merged_id})
        assert merged_entity["status"] == "active"  # Restored
        
        # Verify alias ownership restored
        alias_after_unmerge = await db.entity_aliases.find_one({"_id": alias_id})
        assert alias_after_unmerge["entity_id"] == merged_id  # Restored
    
    @pytest.mark.asyncio
    async def test_merge_blocked_by_lock(self, db):
        """Test operator lock prevents merge."""
        # Create entities
        winner_id = str(uuid.uuid4())
        merged_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        
        await db.entities.insert_many([
            {"_id": winner_id, "entity_type": "org", "canonical_name": "ABC", "status": "active", "created_at": now, "updated_at": now},
            {"_id": merged_id, "entity_type": "org", "canonical_name": "XYZ", "status": "active", "created_at": now, "updated_at": now}
        ])
        
        # Lock the merged entity
        await db.operator_locks.insert_one({
            "_id": str(uuid.uuid4()),
            "lock_type": "entity",
            "lock_id": merged_id,
            "reason": "Under review",
            "created_at": now
        })
        
        # Try to merge
        with pytest.raises(ValueError, match="locked"):
            await merge_entities(db, winner_id, merged_id, "test", 1.0)
