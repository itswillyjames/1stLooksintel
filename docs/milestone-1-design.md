# Milestone 1: MongoDB Schema + Minimal API Design

## MongoDB Collections (All 23 Collections)

### Core Demo Flow Collections (with full service logic in M1)

#### 1. permits
```javascript
{
  _id: "uuid-string",
  city: "Chicago|Seattle|Cincinnati|Denver|Austin",
  source_permit_id: "string",
  filed_date: "ISO-8601",
  issued_date: "ISO-8601",
  address_raw: "string",
  address_norm: "string",
  work_type: "string",
  description_raw: "string",
  valuation: 0,
  applicant_raw: "string",
  contractor_raw: "string",
  owner_raw: "string",
  status: "new|normalized|prequalified|shortlisted|rejected|archived",
  prequal_score: 0.0,
  prequal_reasons: ["string"],  // native array (not JSON string)
  created_at: "ISO-8601",
  updated_at: "ISO-8601"
}
// Indexes:
// { city: 1, filed_date: -1 }
// { status: 1, prequal_score: -1 }
// { address_norm: 1 }
// UNIQUE: { city: 1, source_permit_id: 1 }
```

#### 2. permit_sources
```javascript
{
  _id: "uuid-string",
  permit_id: "uuid-ref",
  source_name: "string",
  source_url: "string",
  raw_payload: {},  // native object
  retrieved_at: "ISO-8601",
  hash: "string"
}
// Index: { permit_id: 1 }
```

#### 3. permit_events
```javascript
{
  _id: "uuid-string",
  permit_id: "uuid-ref",
  event_type: "string",
  event_payload: {},  // native object
  created_at: "ISO-8601"
}
// Index: { permit_id: 1, created_at: -1 }
```

#### 4. reports
```javascript
{
  _id: "uuid-string",
  permit_id: "uuid-ref",
  status: "draft|queued|running|partial|completed|failed|superseded|archived",
  active_version_id: "uuid-ref|null",
  created_at: "ISO-8601",
  updated_at: "ISO-8601"
}
// Index: { permit_id: 1 }
// Index: { status: 1, updated_at: -1 }
```

#### 5. report_versions
```javascript
{
  _id: "uuid-string",
  report_id: "uuid-ref",
  version: 1,
  snapshot: {},  // immutable inputs snapshot
  status: "queued|running|partial|completed|failed",
  created_at: "ISO-8601",
  updated_at: "ISO-8601"
}
// Index: { report_id: 1, version: 1 } UNIQUE
```

#### 6. report_events
```javascript
{
  _id: "uuid-string",
  report_version_id: "uuid-ref",
  event_type: "string",
  event_payload: {},
  created_at: "ISO-8601"
}
// Index: { report_version_id: 1, created_at: -1 }
```

#### 7. stage_attempts
```javascript
{
  _id: "uuid-string",
  report_version_id: "uuid-ref",
  stage_name: "string",
  status: "queued|running|succeeded|retrying|failed_retryable|failed_terminal|skipped",
  idempotency_key: "string",
  provider: "string|null",
  model_id: "string|null",
  attempt_no: 1,
  input_hash: "string",
  started_at: "ISO-8601|null",
  finished_at: "ISO-8601|null",
  error_class: "string|null",
  error_message: "string|null",
  metrics: {},  // { latency_ms, tokens, etc. }
  created_at: "ISO-8601",
  updated_at: "ISO-8601"
}
// Index: { report_version_id: 1, stage_name: 1 }
// Index: { status: 1 }
// UNIQUE: { report_version_id: 1, stage_name: 1, idempotency_key: 1 }
```

#### 8. stage_outputs
```javascript
{
  _id: "uuid-string",
  stage_attempt_id: "uuid-ref",
  output: {},  // validated JSON output
  output_hash: "string",
  created_at: "ISO-8601"
}
// Index: { stage_attempt_id: 1 }
```

#### 9. stage_events
```javascript
{
  _id: "uuid-string",
  stage_attempt_id: "uuid-ref",
  event_type: "string",
  event_payload: {},
  created_at: "ISO-8601"
}
// Index: { stage_attempt_id: 1, created_at: -1 }
```

### Supporting Collections (schema only in M1, minimal/no service logic)

#### 10. evidence_items
```javascript
{
  _id: "uuid-string",
  type: "web_page|registry|pdf|image|note|model_response",
  source: "string",
  title: "string|null",
  retrieved_at: "ISO-8601",
  hash: "string",
  storage_ref: "string",  // inline|kv:key|r2:key
  mime_type: "string|null",
  bytes_len: 0,
  status: "active|deprecated",
  created_at: "ISO-8601"
}
// Index: { hash: 1 }
```

#### 11. evidence_links
```javascript
{
  _id: "uuid-string",
  evidence_id: "uuid-ref",
  link_type: "permit|entity|report_version|export",
  link_id: "uuid-ref",
  created_at: "ISO-8601"
}
// Index: { link_type: 1, link_id: 1 }
// Index: { evidence_id: 1 }
```

#### 12. derived_claims
```javascript
{
  _id: "uuid-string",
  report_version_id: "uuid-ref",
  claim_type: "string",
  claim: {},
  confidence: 0.0,
  evidence_ids: ["uuid-ref"],
  created_at: "ISO-8601"
}
// Index: { report_version_id: 1 }
```

#### 13. entities
```javascript
{
  _id: "uuid-string",
  entity_type: "person|org|place",
  canonical_name: "string",
  city: "string|null",
  status: "active|merged|archived",
  created_at: "ISO-8601",
  updated_at: "ISO-8601"
}
// Index: { canonical_name: 1 }
```

#### 14. entity_aliases
```javascript
{
  _id: "uuid-string",
  entity_id: "uuid-ref",
  alias: "string",
  alias_norm: "string",
  source_evidence_id: "uuid-ref|null",
  address_norm: "string|null",
  phone: "string|null",
  email: "string|null",
  website: "string|null",
  created_at: "ISO-8601"
}
// Index: { entity_id: 1 }
// Index: { alias_norm: 1 }
```

#### 15. entity_identifiers
```javascript
{
  _id: "uuid-string",
  entity_id: "uuid-ref",
  id_type: "license|domain|ein|state_reg",
  id_value: "string",
  source_evidence_id: "uuid-ref|null",
  created_at: "ISO-8601"
}
// Index: { entity_id: 1 }
// UNIQUE: { id_type: 1, id_value: 1 }
```

#### 16. entity_links
```javascript
{
  _id: "uuid-string",
  from_entity_id: "uuid-ref",
  to_entity_id: "uuid-ref",
  link_type: "owner_of|contractor_for|architect_for|contact_of",
  confidence: 0.0,
  evidence_ids: ["uuid-ref"],
  created_at: "ISO-8601"
}
// Index: { from_entity_id: 1 }
// Index: { to_entity_id: 1 }
```

#### 17. merge_ledger
```javascript
{
  _id: "uuid-string",
  winner_entity_id: "uuid-ref",
  merged_entity_id: "uuid-ref",
  rule: "string",
  confidence: 0.0,
  operator_decision: "approved|rejected",
  diff: {},
  created_at: "ISO-8601"
}
// Index: { winner_entity_id: 1 }
// Index: { merged_entity_id: 1 }
```

#### 18. unmerge_ledger
```javascript
{
  _id: "uuid-string",
  merge_ledger_id: "uuid-ref",
  operator_note: "string|null",
  diff: {},
  created_at: "ISO-8601"
}
// Index: { merge_ledger_id: 1 }
```

#### 19. operator_locks
```javascript
{
  _id: "uuid-string",
  lock_type: "entity|alias|identifier",
  lock_id: "uuid-ref",
  reason: "string|null",
  created_at: "ISO-8601"
}
// UNIQUE: { lock_type: 1, lock_id: 1 }
```

#### 20. exports
```javascript
{
  _id: "uuid-string",
  report_version_id: "uuid-ref",
  export_type: "dossier|playbook|bundle",
  template_version: "string",
  status: "draft|rendering|ready|delivered|failed",
  html_storage_ref: "string|null",
  pdf_storage_ref: "string|null",
  checksum_html: "string|null",
  checksum_pdf: "string|null",
  created_at: "ISO-8601",
  updated_at: "ISO-8601"
}
// Index: { report_version_id: 1, status: 1 }
```

#### 21. export_events
```javascript
{
  _id: "uuid-string",
  export_id: "uuid-ref",
  event_type: "string",
  event_payload: {},
  created_at: "ISO-8601"
}
// Index: { export_id: 1, created_at: -1 }
```

#### 22. report_outcomes
```javascript
{
  _id: "uuid-string",
  report_id: "uuid-ref",
  outcome_type: "sold|lost|in_progress|invalid",
  revenue_cents: 0,
  notes: "string|null",
  created_at: "ISO-8601"
}
// Index: { report_id: 1 }
```

#### 23. comparables
```javascript
{
  _id: "uuid-string",
  report_version_id: "uuid-ref",
  comparable: {},
  created_at: "ISO-8601"
}
// Index: { report_version_id: 1 }
```

---

## Minimal API Endpoints (Milestone 1)

### 1. GET /api/permits
**Query params:**
- `city` (optional): filter by city
- `status` (optional): filter by status
- `min_score` (optional): filter by prequal_score >= min_score
- `limit` (default: 50)
- `skip` (default: 0)

**Response:**
```json
{
  "permits": [
    {
      "_id": "uuid",
      "city": "Chicago",
      "source_permit_id": "2024-12345",
      "filed_date": "2024-01-15T00:00:00Z",
      "address_raw": "123 Main St",
      "work_type": "new_construction",
      "valuation": 1500000,
      "status": "prequalified",
      "prequal_score": 85.5,
      "prequal_reasons": ["High valuation", "Commercial project"],
      "created_at": "2024-01-16T10:00:00Z",
      "updated_at": "2024-01-16T10:00:00Z"
    }
  ],
  "total": 12
}
```

### 2. POST /api/permits/seed
**Body:** (optional, or can be empty to use defaults)
```json
{
  "force": false  // if true, delete existing and reseed
}
```

**Response:**
```json
{
  "message": "Seeded 10 permits",
  "permits_created": 10,
  "already_existed": 0
}
```

### 3. POST /api/reports
**Body:**
```json
{
  "permit_id": "uuid"
}
```

**Response:**
```json
{
  "_id": "uuid",
  "permit_id": "uuid",
  "status": "draft",
  "active_version_id": null,
  "created_at": "2024-01-16T12:00:00Z",
  "updated_at": "2024-01-16T12:00:00Z"
}
```

### 4. POST /api/reports/{report_id}/versions
**Body:** (optional override snapshot fields)
```json
{
  "snapshot_override": {}  // optional
}
```

**Response:**
```json
{
  "_id": "uuid",
  "report_id": "uuid",
  "version": 1,
  "snapshot": {
    "permit": { /* permit data as-of-run */ },
    "operator_notes": "",
    "run_config": {}
  },
  "status": "queued",
  "created_at": "2024-01-16T12:01:00Z",
  "updated_at": "2024-01-16T12:01:00Z"
}
```

### 5. GET /api/reports/{report_id}
**Response:**
```json
{
  "_id": "uuid",
  "permit_id": "uuid",
  "status": "completed",
  "active_version_id": "uuid",
  "created_at": "2024-01-16T12:00:00Z",
  "updated_at": "2024-01-16T12:15:00Z",
  "permit": { /* denormalized permit data */ }
}
```

### 6. GET /api/report_versions/{version_id}/stage_attempts
**Response:**
```json
{
  "report_version_id": "uuid",
  "stage_attempts": [
    {
      "_id": "uuid",
      "stage_name": "permit_parse",
      "status": "succeeded",
      "provider": "openai",
      "model_id": "gpt-4o",
      "attempt_no": 1,
      "started_at": "2024-01-16T12:01:05Z",
      "finished_at": "2024-01-16T12:01:12Z",
      "metrics": {
        "latency_ms": 7200,
        "input_tokens": 150,
        "output_tokens": 80
      }
    }
  ]
}
```

---

## Seed Data (Golden Records)

### 3 Cities × ~3 permits each = 10 permits total

**Chicago (4 permits):**
1. High-value commercial new construction ($2.5M)
2. Mixed-use renovation ($850K)
3. Low-value residential addition ($45K) — noise
4. Industrial warehouse build-out ($1.2M)

**Seattle (3 permits):**
1. Commercial tenant improvement ($950K)
2. Institutional school renovation ($3.1M)
3. Residential ADU ($75K) — noise

**Cincinnati (3 permits):**
1. Commercial retail build-out ($780K)
2. Industrial manufacturing expansion ($1.8M)
3. Residential deck addition ($12K) — noise

### Prequalification Scoring (Deterministic)
- Valuation >= $750K → +40 points
- Work type = commercial|industrial|institutional → +30 points
- Project keywords (new construction, tenant improvement, expansion) → +15 points
- Base score: 15
- Reject threshold: < 50 (noise)
- Shortlist threshold: >= 70

---

## Verification Steps (Milestone 1 Complete)

1. **Seed idempotency:**
   ```bash
   curl -X POST http://localhost:8001/api/permits/seed
   # Returns: "permits_created": 10
   
   curl -X POST http://localhost:8001/api/permits/seed
   # Returns: "already_existed": 10, "permits_created": 0
   ```

2. **Filter permits:**
   ```bash
   curl "http://localhost:8001/api/permits?city=Chicago&min_score=70"
   # Returns 3 high-score permits (not the $45K noise)
   ```

3. **Create report + version:**
   ```bash
   permit_id=$(curl http://localhost:8001/api/permits?limit=1 | jq -r '.permits[0]._id')
   
   report_id=$(curl -X POST http://localhost:8001/api/reports \
     -H "Content-Type: application/json" \
     -d "{\"permit_id\": \"$permit_id\"}" | jq -r '._id')
   
   version_id=$(curl -X POST http://localhost:8001/api/reports/$report_id/versions \
     -H "Content-Type: application/json" \
     -d '{}' | jq -r '._id')
   
   curl http://localhost:8001/api/reports/$report_id
   # Should show active_version_id = $version_id
   ```

4. **Check stage attempts (empty for now):**
   ```bash
   curl http://localhost:8001/api/report_versions/$version_id/stage_attempts
   # Returns: "stage_attempts": []
   ```

---

## Files to Create

1. `/app/backend/app/__init__.py`
2. `/app/backend/app/db/__init__.py`
3. `/app/backend/app/db/collections.py` — Collection definitions + index creation
4. `/app/backend/app/db/seed.py` — Seed fixtures
5. `/app/backend/app/models/__init__.py`
6. `/app/backend/app/models/permit.py` — Pydantic models for permits
7. `/app/backend/app/models/report.py` — Pydantic models for reports
8. `/app/backend/app/services/__init__.py`
9. `/app/backend/app/services/permit_service.py` — Permit business logic
10. `/app/backend/app/services/report_service.py` — Report business logic
11. `/app/backend/app/api/__init__.py`
12. `/app/backend/app/api/permits.py` — Permit endpoints
13. `/app/backend/app/api/reports.py` — Report endpoints
14. `/app/backend/server.py` — Update with new routers
15. `/app/docs/01-Architecture-Spec-Revised.md` — Copy design doc
16. `/app/docs/02-Migration-and-Contracts-Appendix-Revised.md` — Copy design doc

---

## Acceptance Checklist

- [ ] All 23 collections created with correct indexes
- [ ] Seed script runs idempotently (UNIQUE constraint on city + source_permit_id)
- [ ] 10 permits seeded across 3 cities
- [ ] Prequalification scores computed correctly
- [ ] GET /api/permits filters work (city, status, min_score)
- [ ] POST /api/reports creates draft report
- [ ] POST /api/reports/{id}/versions creates immutable snapshot
- [ ] reports.active_version_id updates correctly
- [ ] GET /api/report_versions/{id}/stage_attempts returns empty list (no stages run yet)
- [ ] No UI generated (backend only)
