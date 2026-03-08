# MILESTONE 5: Export HTML Dossier + Manifest

**Status:** COMPLETE  
**Date:** 2025-01-XX  
**Tests:** 11/11 export tests + 40/40 full suite passing

---

## Summary

Milestone 5 implements HTML dossier export with a manifest JSON that references all data sources used. The export is versioned, idempotent, and produces deterministic output for the same inputs.

---

## Endpoints Added

### Canonical Routes (in `/api/reports`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/reports/versions/{version_id}/exports/dossier/render` | Render HTML dossier export |
| `GET` | `/api/reports/versions/{version_id}/exports` | List exports for a report version |

### Export Routes (in `/api/exports`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/exports/{export_id}` | Get export by ID (supports `?format=html` for raw HTML) |
| `GET` | `/api/exports/by-version/{version_id}` | List exports (alias route) |

---

## Template Fields (v1)

The HTML dossier template includes:

| Section | Fields |
|---------|--------|
| **Permit Information** | address, city, permit_id, work_type, description, valuation, filed_date, owner, contractor |
| **Scope Summary** | project_type, scope_summary, estimated_size, buyer_fit_score, buyer_fit_rationale |
| **Extracted Entities** | canonical_name, entity_type, status |
| **Entity Match Suggestions** | observed_name, observed_role, match_type, status |

---

## Manifest Schema

```json
{
  "export_id": "uuid",
  "report_version_id": "uuid",
  "export_type": "html_dossier",
  "template_version": "v1",
  "rendered_at": "ISO8601",
  
  "stage_attempts": [
    {
      "stage_name": "scope_summary",
      "attempt_id": "uuid",
      "status": "succeeded"
    }
  ],
  
  "entities": [
    {
      "entity_id": "uuid",
      "canonical_name": "BuildRight Construction",
      "entity_type": "organization",
      "status": "active"
    }
  ],
  
  "entity_suggestions": [
    {
      "suggestion_id": "uuid",
      "observed_name": "BuildRight Construction",
      "observed_role": "contractor",
      "match_type": "exact",
      "status": "open"
    }
  ],
  
  "evidence_links": [
    {
      "evidence_id": "uuid",
      "link_type": "report_version",
      "link_id": "uuid"
    }
  ],
  
  "permit_snapshot": { /* full permit data at time of report version */ },
  "run_config_snapshot": { /* run config from report version */ }
}
```

---

## Export Document Schema

```json
{
  "_id": "uuid",
  "report_version_id": "uuid",
  "export_type": "html_dossier",
  "template_version": "v1",
  "status": "draft|rendering|ready|delivered|failed",
  "html_content": "<html>...</html>",
  "manifest": { /* see above */ },
  "idempotency_key": "uuid",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

---

## Idempotency

Exports are idempotent via unique index on `(report_version_id, export_type, template_version)`.

- First render: Creates new export, returns `is_rerun: false`
- Subsequent renders: Returns existing export, returns `is_rerun: true`

---

## curl Verification Commands

### 1. Render HTML dossier for a report_version

```bash
API_URL=$(grep REACT_APP_BACKEND_URL /app/frontend/.env | cut -d '=' -f2)

# Use an existing report_version_id
VERSION_ID="<your-report-version-id>"

curl -X POST "$API_URL/api/reports/versions/$VERSION_ID/exports/dossier/render" \
  -H "Content-Type: application/json" \
  -d '{"template_version": "v1"}' | python3 -m json.tool
```

**Expected Response:**
```json
{
  "export": {
    "id": "export-uuid",
    "report_version_id": "version-uuid",
    "export_type": "html_dossier",
    "template_version": "v1",
    "status": "ready",
    "manifest": { ... },
    "idempotency_key": "...",
    "created_at": "2025-01-...",
    "updated_at": "2025-01-..."
  },
  "is_rerun": false
}
```

### 2. List exports for a report_version

```bash
curl -X GET "$API_URL/api/reports/versions/$VERSION_ID/exports" \
  -H "Content-Type: application/json" | python3 -m json.tool
```

**Expected Response:**
```json
{
  "report_version_id": "version-uuid",
  "exports": [
    {
      "id": "export-uuid",
      "report_version_id": "version-uuid",
      "export_type": "html_dossier",
      "template_version": "v1",
      "status": "ready",
      "idempotency_key": "...",
      "created_at": "2025-01-...",
      "updated_at": "2025-01-..."
    }
  ]
}
```

### 3. Get export by ID (JSON)

```bash
EXPORT_ID="<export-id-from-step-1>"

curl -X GET "$API_URL/api/exports/$EXPORT_ID" \
  -H "Content-Type: application/json" | python3 -m json.tool
```

### 4. Get export by ID (raw HTML)

```bash
curl -X GET "$API_URL/api/exports/$EXPORT_ID?format=html"
```

**Expected Response:** Raw HTML document

### 5. Verify idempotency (rerun returns same export_id)

```bash
# Run the same render command again
curl -X POST "$API_URL/api/reports/versions/$VERSION_ID/exports/dossier/render" \
  -H "Content-Type: application/json" \
  -d '{"template_version": "v1"}' | python3 -m json.tool

# Should return is_rerun: true with same export_id
```

---

## Files Created/Modified

### New Files
- `/app/backend/app/models/export.py` - Export Pydantic models
- `/app/backend/app/services/export_service.py` - HTML rendering, manifest building
- `/app/backend/app/api/exports.py` - Export API endpoints
- `/app/backend/tests/test_exports.py` - 11 unit tests for M5

### Modified Files
- `/app/backend/app/api/reports.py` - Added canonical export routes
- `/app/backend/server.py` - Included exports router

---

## Design Decisions

1. **HTML-only export** - No PDF generation to avoid new infrastructure/cost
2. **Deterministic rendering** - Entities and suggestions sorted by name for stable output
3. **Immutable evidence** - evidence_items/evidence_links are read-only, never mutated
4. **Template versioning** - `template_version` field enables future template evolution
5. **Manifest completeness** - References all source data (stages, entities, suggestions, evidence)

---

## State Machine

Export status transitions (defined in Milestone 2):

```
draft -> rendering -> ready -> delivered
                  \-> failed -> rendering (retry)
```

---

## Quick Links

- [Milestone 1](./MILESTONE-1-COMPLETE.md) - Data Model + Persistence
- [Milestone 2](./MILESTONE-2-COMPLETE.md) - State Machines
- [Milestone 2.1](./MILESTONE-2_1-COMPLETE.md) - Documentation Patch
- [Milestone 3](./MILESTONE-3-COMPLETE.md) - Pipeline Skeleton
- [Milestone 4](./MILESTONE-4-COMPLETE.md) - Entity Resolution
- [Design Doc](./milestone-1-design.md) - Original specifications
