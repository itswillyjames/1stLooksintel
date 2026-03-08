# Milestone 2: Canonical State Machines + Transition Validators — COMPLETE ✓

**Completed:** 2026-03-08
**Status:** All acceptance criteria met

---

## What Changed

### 1. State Machine Module Created (`/app/backend/app/state_machine/`)
- **`enums.py`**: Canonical status enums (single source of truth)
  - `PermitStatus`: new | normalized | prequalified | shortlisted | rejected | archived
  - `ReportStatus`: draft | queued | running | partial | completed | failed | superseded | archived
  - `ReportVersionStatus`: queued | running | partial | completed | failed
  - `StageAttemptStatus`: queued | running | succeeded | failed
  - `ExportStatus`: draft | rendering | ready | delivered | failed

- **`validators.py`**: Transition validation functions
  - `can_transition_permit(from, to, context)` → (is_valid, reason)
  - `can_transition_report(from, to, context)` → (is_valid, reason)
  - `can_transition_report_version(from, to, context)` → (is_valid, reason)
  - `can_transition_stage_attempt(from, to, context)` → (is_valid, reason)
  - `can_transition_export(from, to, context)` → (is_valid, reason)

- **`events.py`**: Event emission helpers
  - `emit_event(db, collection_name, entity_id_field, entity_id, event_type, payload)`
  - `emit_status_change_event(db, collection_name, entity_id_field, entity_id, from, to, reason)`

### 2. Service Layer Integration
- **`permit_service.py`**: Added `transition_permit_status(db, permit_id, to_status, reason)`
- **`report_service.py`**: Added:
  - `transition_report_status(db, report_id, to_status, reason)`
  - `transition_report_version_status(db, version_id, to_status, reason)`

All service functions:
- Validate transitions using state machine validators
- Update status atomically
- Emit append-only events on success
- Raise `ValueError("INVALID_TRANSITION: ...")` on invalid transitions

### 3. API Endpoints Added
- **`POST /api/permits/{permit_id}/status`**
  - Body: `{"status": "...", "reason": "..."}`
  - Returns: Updated permit or 400 with INVALID_TRANSITION error

- **`POST /api/reports/{report_id}/status`**
  - Body: `{"status": "...", "reason": "..."}`
  - Returns: Updated report or 400 with INVALID_TRANSITION error

- **`POST /api/reports/versions/{version_id}/status`**
  - Body: `{"status": "...", "reason": "..."}`
  - Returns: Updated version or 400 with INVALID_TRANSITION error

Error response format:
```json
{
  "detail": {
    "error": "INVALID_TRANSITION",
    "from": "normalized",
    "to": "new",
    "reason": "Invalid transition: normalized -> new"
  }
}
```

### 4. Automated Tests Created (`/app/backend/tests/`)
- **`test_state_machines.py`** (12 tests, all passing):
  - `TestPermitTransitions`: 3 tests (allowed, blocked, event emission)
  - `TestReportTransitions`: 2 tests (allowed, blocked with context validation)
  - `TestReportVersionTransitions`: 2 tests (allowed, terminal states)
  - `TestStageAttemptTransitions`: 2 tests (allowed, terminal states)
  - `TestExportTransitions`: 2 tests (allowed, terminal state)
  - `TestEventEmission`: 1 test (immutability verification)

---

## Files Changed

### Created:
1. `/app/backend/app/state_machine/__init__.py`
2. `/app/backend/app/state_machine/enums.py`
3. `/app/backend/app/state_machine/validators.py`
4. `/app/backend/app/state_machine/events.py`
5. `/app/backend/tests/__init__.py`
6. `/app/backend/tests/test_state_machines.py`

### Modified:
1. `/app/backend/app/services/permit_service.py` — Added transition function
2. `/app/backend/app/services/report_service.py` — Added transition functions
3. `/app/backend/app/api/permits.py` — Added status transition endpoint
4. `/app/backend/app/api/reports.py` — Added status transition endpoints
5. `/app/backend/requirements.txt` — Added pytest-asyncio

---

## Verification Results

### Test Suite: All 12 Tests Pass ✓
```bash
cd /app/backend
python -m pytest tests/test_state_machines.py -v

============================== 12 passed in 0.18s ==============================
```

### Manual API Tests

#### 1. Valid Transition ✓
```bash
# new -> normalized
curl -X POST /api/permits/{id}/status \
  -d '{"status": "normalized", "reason": "test"}' 

Response: {"status": "normalized", ...}
```

#### 2. Invalid Transition Blocked ✓
```bash
# normalized -> new (backwards)
curl -X POST /api/permits/{id}/status \
  -d '{"status": "new"}'

Response: {
  "detail": {
    "error": "INVALID_TRANSITION",
    "from": "normalized",
    "to": "new",
    "reason": "Invalid transition: normalized -> new"
  }
}
```

#### 3. Self-Transition Blocked ✓
```bash
# normalized -> normalized
curl -X POST /api/permits/{id}/status \
  -d '{"status": "normalized"}'

Response: {
  "detail": {
    "error": "INVALID_TRANSITION",
    "reason": "Cannot transition to the same status"
  }
}
```

#### 4. Terminal State Blocked ✓
```bash
# archived -> anything
curl -X POST /api/permits/{archived_id}/status \
  -d '{"status": "prequalified"}'

Response: {
  "detail": {
    "error": "INVALID_TRANSITION",
    "reason": "Cannot transition from archived (terminal state)"
  }
}
```

#### 5. Context Validation ✓
```bash
# draft -> queued without active_version_id
curl -X POST /api/reports/{id}/status \
  -d '{"status": "queued"}'

Response: {
  "detail": {
    "error": "INVALID_TRANSITION",
    "reason": "Cannot queue report without active version"
  }
}
```

#### 6. Event Emission Verified ✓
```python
# MongoDB query after transition
db.permit_events.find({"permit_id": "..."})

Result: {
  "_id": "...",
  "permit_id": "...",
  "event_type": "status_changed",
  "event_payload": {
    "from_status": "new",
    "to_status": "normalized",
    "reason": "test transition"
  },
  "created_at": "2026-03-08T18:30:00Z"
}
```

---

## Transition Rules Implemented

### Permit
```
new → normalized
normalized → prequalified | rejected
prequalified → shortlisted | rejected | archived
shortlisted → archived
rejected → archived
archived = TERMINAL (no outgoing transitions)
```

### Report
```
draft → queued (requires active_version_id)
queued → running
running → partial | completed | failed
partial → running | completed | failed
completed → superseded | archived
failed → queued | archived
superseded → archived
archived = TERMINAL
```

### Report Version
```
queued → running
running → partial | completed | failed
partial → running | completed | failed
completed = TERMINAL
failed = TERMINAL
```

### Stage Attempt
```
queued → running
running → succeeded | failed
succeeded = TERMINAL
failed = TERMINAL
```

### Export
```
draft → rendering
rendering → ready | failed
ready → delivered | failed
failed → rendering (retry)
delivered = TERMINAL
```

---

## Event Schema

All events follow this structure:
```json
{
  "_id": "uuid",
  "{entity}_id": "entity-uuid",
  "event_type": "status_changed",
  "event_payload": {
    "from_status": "...",
    "to_status": "...",
    "reason": "..."
  },
  "created_at": "ISO-8601"
}
```

Event collections:
- `permit_events` (entity_id_field: `permit_id`)
- `report_events` (entity_id_field: `report_id` or `report_version_id`)
- `stage_events` (entity_id_field: `stage_attempt_id`)
- `export_events` (entity_id_field: `export_id`)

**IMMUTABILITY ENFORCED**: Events are append-only. No update or delete methods exist in service layer or API.

---

## Acceptance Checklist

- [x] State machine definitions (enums) as single source of truth
- [x] Transition validators for all 5 entity types
- [x] Terminal states properly enforced (archived, completed, failed, succeeded, delivered)
- [x] Context validation (e.g., report requires active_version_id to queue)
- [x] Event emission on every successful transition
- [x] Events are append-only (no update/delete endpoints)
- [x] Service layer integration (permit_service, report_service)
- [x] API endpoints for status transitions
- [x] Structured INVALID_TRANSITION errors (400 status code)
- [x] Automated tests (12 tests, all passing)
- [x] Tests verify allowed transitions succeed
- [x] Tests verify blocked transitions fail with INVALID_TRANSITION
- [x] Tests verify event documents are created
- [x] Tests verify terminal states block outgoing transitions
- [x] Tests verify context validation rules
- [x] No UI generated (backend only)
- [x] No pipeline execution added (deferred to Milestone 3)

---

## Usage Examples

### Permit Workflow
```bash
API_URL="https://intel-scope-1.preview.emergentagent.com"

# 1. Get a permit
PERMIT_ID=$(curl "$API_URL/api/permits?status=new&limit=1" | jq -r '.permits[0].id')

# 2. Normalize
curl -X POST "$API_URL/api/permits/$PERMIT_ID/status" \
  -H "Content-Type: application/json" \
  -d '{"status": "normalized", "reason": "automated normalization"}'

# 3. Prequalify
curl -X POST "$API_URL/api/permits/$PERMIT_ID/status" \
  -H "Content-Type: application/json" \
  -d '{"status": "prequalified", "reason": "scored above threshold"}'

# 4. Shortlist
curl -X POST "$API_URL/api/permits/$PERMIT_ID/status" \
  -H "Content-Type: application/json" \
  -d '{"status": "shortlisted", "reason": "high value commercial"}'

# 5. Query events
mongo test_database --eval "db.permit_events.find({permit_id: '$PERMIT_ID'})"
```

### Report Workflow
```bash
# 1. Create report (draft)
REPORT_ID=$(curl -X POST "$API_URL/api/reports" \
  -H "Content-Type: application/json" \
  -d '{"permit_id": "..."}' | jq -r '.id')

# 2. Create version (auto-queues report)
VERSION_ID=$(curl -X POST "$API_URL/api/reports/$REPORT_ID/versions" \
  -H "Content-Type: application/json" \
  -d '{}' | jq -r '.id')

# 3. Start report
curl -X POST "$API_URL/api/reports/$REPORT_ID/status" \
  -H "Content-Type: application/json" \
  -d '{"status": "running"}'

# 4. Start version execution
curl -X POST "$API_URL/api/reports/versions/$VERSION_ID/status" \
  -H "Content-Type: application/json" \
  -d '{"status": "running"}'

# 5. Complete version
curl -X POST "$API_URL/api/reports/versions/$VERSION_ID/status" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'

# 6. Complete report
curl -X POST "$API_URL/api/reports/$REPORT_ID/status" \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

---

## Design Decisions

### 1. Validator Return Format
Returns `(is_valid: bool, reason: str)` for clarity. Services can easily check validity and provide detailed error messages to API consumers.

### 2. Context Parameter
Optional `context` dict allows validators to check additional conditions (e.g., `has_active_version`). This keeps validators pure functions without database dependencies.

### 3. Event Emission Location
Events are emitted in service layer (not API layer) to ensure all transitions—whether triggered by API, internal processes, or future workers—are logged consistently.

### 4. Separate Events for Report vs ReportVersion
Report-level events use `report_id`, version-level events use `report_version_id`. This maintains clear separation between container (report) and execution (version).

### 5. Terminal States Philosophy
- **Hard terminals** (no outgoing): archived, completed, failed, succeeded, delivered
- **Soft terminals** (can retry): failed (for exports only - can retry rendering)

### 6. Error Response Structure
Structured JSON with `error`, `from`, `to`, `reason` fields allows frontend to:
- Display user-friendly messages
- Highlight the invalid transition
- Log detailed error reasons for debugging

---

## Next Steps

### Milestone 3: Pipeline Skeleton (1 Real Stage)
- Implement orchestrator for report_version stages
- Stage runner interface with strict JSON validation
- Attempt logs with timing/provider/model fields
- Idempotency using idempotency_key
- ONE end-to-end stage (e.g., `scope_summary`)
- Integrate with state machine (queued → running → succeeded/failed)

### Milestone 4: Entity Resolution
- Entity graph creation from extracted entities
- Match tiers + review queue
- Merge/unmerge with lineage

### Milestone 5: Export HTML Dossier
- Template versioning
- HTML renderer
- PDF derivation
- Export manifest

### Milestone 6: Operator UI
- Permit list + filters + shortlist
- Report run controls + stage status
- Entity review + merge/unmerge screens
- Export view + download

---

**Milestone 2 Status: COMPLETE ✓**

All acceptance criteria met. State machines enforce transitions, events are emitted, tests pass, API endpoints work correctly.
