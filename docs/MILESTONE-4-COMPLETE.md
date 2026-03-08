# MILESTONE 4: Entity Resolution + Merge/Unmerge

**Status:** COMPLETE  
**Date:** 2025-01-XX  
**Tests:** 8/8 entity tests + 29/29 full suite passing

---

## Summary

Milestone 4 implements deterministic entity resolution with safe-by-default merge/unmerge semantics. The system extracts entities from permit data, generates match suggestions for operator review, and maintains a complete audit trail for all merge operations.

---

## Endpoints Added

### Entity Extraction (in `/api/reports`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/reports/versions/{version_id}/entities/extract` | Extract entities from report version snapshot |
| `GET` | `/api/reports/versions/{version_id}/entity_suggestions` | List match suggestions for operator review |

### Entity Merge/Unmerge (in `/api/entities`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/entities/merge` | Merge two entities (winner absorbs merged) |
| `POST` | `/api/entities/unmerge` | Reverse a merge using stored diff |

---

## Schema/Indexes Added

### New Collection: `entity_match_suggestions`

```javascript
{
  "_id": "uuid",
  "report_version_id": "uuid",
  "observed_name": "Reliable Builders Inc",
  "observed_role": "contractor",
  "observed_source": "permit.contractor_raw",
  "alias_norm": "reliable builders inc",
  "candidate_entity_ids": ["uuid1", "uuid2"],
  "match_type": "exact|fuzzy",
  "confidence": 0.95,
  "status": "open|approved|rejected",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

### Indexes

```python
# entity_match_suggestions indexes
await db.entity_match_suggestions.create_index([("report_version_id", 1)])
await db.entity_match_suggestions.create_index([("status", 1)])
await db.entity_match_suggestions.create_index([("alias_norm", 1)])
```

---

## Merge/Unmerge Diff Strategy

### diff_json Structure (stored in merge_ledger)

```json
{
  "merged_entity_id": "uuid-of-entity-being-absorbed",
  "merged_entity_previous_status": "active",
  "merged_alias_ids": ["alias-uuid-1", "alias-uuid-2"],
  "merged_identifier_ids": ["identifier-uuid-1"],
  "merged_link_from_ids": ["link-uuid-1"],
  "merged_link_to_ids": ["link-uuid-2", "link-uuid-3"]
}
```

### Merge Operation

1. Verify both entities exist and are not locked
2. Capture current state of merged entity (aliases, identifiers, links)
3. Create `merge_ledger` entry with diff
4. Set merged entity `status="merged"`
5. Re-point all aliases to winner (`entity_id = winner_entity_id`)
6. Re-point all identifiers to winner
7. Re-point all links (both `from_entity_id` and `to_entity_id`)

### Unmerge Operation (Reversal)

1. Retrieve `merge_ledger` entry by ID
2. Create `unmerge_ledger` entry for audit trail
3. Restore merged entity status to previous value
4. Restore alias ownership (point back to merged entity)
5. Restore identifier ownership
6. Restore link ownership (both directions)

---

## curl Verification Commands

### 1. Extract entities for a report_version

```bash
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

# First, get a report_version_id from an existing report
VERSION_ID="<your-report-version-id>"

curl -X POST "$API_URL/api/reports/versions/$VERSION_ID/entities/extract" \
  -H "Content-Type: application/json" | python3 -m json.tool
```

**Expected Response:**
```json
{
  "created_entities": ["entity-uuid-1", "entity-uuid-2"],
  "created_aliases": ["alias-uuid-1", "alias-uuid-2"],
  "suggestions_created": ["suggestion-uuid-1"],
  "skipped_locked": []
}
```

### 2. List suggestions

```bash
curl -X GET "$API_URL/api/reports/versions/$VERSION_ID/entity_suggestions?status=open" \
  -H "Content-Type: application/json" | python3 -m json.tool
```

**Expected Response:**
```json
{
  "suggestions": [
    {
      "id": "suggestion-uuid",
      "observed_name": "Reliable Builders Inc",
      "observed_role": "contractor",
      "observed_source": "permit.contractor_raw",
      "alias_norm": "reliable builders inc",
      "candidate_entity_ids": ["entity-1", "entity-2"],
      "match_type": "exact",
      "confidence": 1.0,
      "status": "open",
      "created_at": "2025-01-...",
      "updated_at": "2025-01-..."
    }
  ]
}
```

### 3. Merge two entities

```bash
curl -X POST "$API_URL/api/entities/merge" \
  -H "Content-Type: application/json" \
  -d '{
    "winner_entity_id": "entity-uuid-winner",
    "merged_entity_id": "entity-uuid-to-merge",
    "rule": "exact_match",
    "confidence": 1.0,
    "operator_decision": "approved"
  }' | python3 -m json.tool
```

**Expected Response:**
```json
{
  "merge_ledger_id": "merge-ledger-uuid",
  "winner_entity_id": "entity-uuid-winner",
  "merged_entity_id": "entity-uuid-to-merge",
  "rule": "exact_match",
  "confidence": 1.0,
  "created_at": "2025-01-..."
}
```

### 4. Unmerge

```bash
curl -X POST "$API_URL/api/entities/unmerge" \
  -H "Content-Type: application/json" \
  -d '{
    "merge_ledger_id": "merge-ledger-uuid-from-step-3",
    "operator_note": "Operator requested reversal"
  }' | python3 -m json.tool
```

**Expected Response:**
```json
{
  "unmerge_ledger_id": "unmerge-ledger-uuid",
  "merge_ledger_id": "merge-ledger-uuid",
  "operator_note": "Operator requested reversal",
  "created_at": "2025-01-..."
}
```

---

## Files Created/Modified

### New Files
- `/app/backend/app/entities/__init__.py` - Package exports
- `/app/backend/app/entities/canonicalization.py` - Name normalization utilities
- `/app/backend/app/entities/extraction.py` - Entity extraction from report versions
- `/app/backend/app/entities/merge_service.py` - Merge/unmerge logic with ledgering
- `/app/backend/app/api/entities.py` - Merge/unmerge API endpoints
- `/app/backend/tests/test_entities.py` - 8 unit tests for M4

### Modified Files
- `/app/backend/app/db/collections.py` - Added `entity_match_suggestions` collection + indexes
- `/app/backend/app/api/reports.py` - Added entity extraction endpoints
- `/app/backend/server.py` - Included entities router
- `/app/backend/requirements.txt` - Added `rapidfuzz==3.14.3`

---

## Invariants Verified

| # | Invariant | Status |
|---|-----------|--------|
| 1 | `merge_entities` repoints ALL references (aliases, identifiers, links both directions) | ✅ |
| 2 | `merge_entities` sets merged entity `status="merged"`, winner unchanged | ✅ |
| 3 | `merge_ledger.diff` contains sufficient data to reverse merge | ✅ |
| 4 | `unmerge_entities` restores entity status, alias/identifier/link ownership | ✅ |
| 5 | `operator_locks` blocks merges and suggestions for locked entities | ✅ |

---

## Quick Links

- [Milestone 1](./MILESTONE-1-COMPLETE.md) - Data Model + Persistence
- [Milestone 2](./MILESTONE-2-COMPLETE.md) - State Machines
- [Milestone 2.1](./MILESTONE-2_1-COMPLETE.md) - Documentation Patch
- [Milestone 3](./MILESTONE-3-COMPLETE.md) - Pipeline Skeleton
- [Design Doc](./milestone-1-design.md) - Original specifications
