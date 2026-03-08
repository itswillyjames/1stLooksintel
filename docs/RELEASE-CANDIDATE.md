# Permit Intel - Release Candidate v1.0

**Date:** 2025-01-XX  
**Status:** Release Candidate  
**Backend Tests:** 40/40 passing  
**Frontend Lint:** Clean

---

## System Overview

**Permit Intel** is a single-tenant, solo-operator permit intelligence workbench built for analyzing construction permits, extracting entities, and generating exportable dossiers.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Permits  │ │ Pipeline │ │ Entities │ │   Exports    │   │
│  │   List   │ │   Tab    │ │   Tab    │ │  + Preview   │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ Permits  │ │ Reports  │ │ Entities │ │   Exports    │   │
│  │   API    │ │   API    │ │   API    │ │     API      │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────┘   │
│                              │                               │
│  ┌───────────────────────────┴───────────────────────────┐  │
│  │              State Machine + Pipeline                  │  │
│  │     (Status transitions, Idempotency, Validation)     │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      MongoDB (24 Collections)                │
│  permits, reports, report_versions, stage_attempts,         │
│  entities, exports, merge_ledger, ...                       │
└─────────────────────────────────────────────────────────────┘
```

### Core Workflow

1. **Ingest** → Permits seeded/imported into system
2. **Report** → Create report + version (immutable snapshot)
3. **Pipeline** → Run enrichment stages (scope_summary)
4. **Entities** → Extract and resolve entities from permit data
5. **Export** → Render HTML dossier with manifest

---

## API Route Inventory

### Permits API (`/api/permits`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/permits` | List permits with filters |
| `GET` | `/api/permits/{id}` | Get permit by ID |
| `POST` | `/api/permits/seed` | Idempotent seeding |
| `POST` | `/api/permits/{id}/status` | Transition permit status |

### Reports API (`/api/reports`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/reports` | Create report for permit |
| `GET` | `/api/reports/{id}` | Get report with permit data |
| `GET` | `/api/reports/by-permit/{permit_id}` | Get report by permit ID |
| `POST` | `/api/reports/{id}/versions` | Create new version |
| `POST` | `/api/reports/{id}/status` | Transition report status |
| `GET` | `/api/reports/versions/{id}` | Get version details |
| `POST` | `/api/reports/versions/{id}/status` | Transition version status |
| `GET` | `/api/reports/versions/{id}/stage_attempts` | List stage attempts |
| `GET` | `/api/reports/stage_attempts/{id}` | Get attempt + output |
| `POST` | `/api/reports/versions/{id}/stages/scope_summary/run` | Run scope_summary |
| `POST` | `/api/reports/versions/{id}/entities/extract` | Extract entities |
| `GET` | `/api/reports/versions/{id}/entity_suggestions` | List suggestions |
| `POST` | `/api/reports/versions/{id}/exports/dossier/render` | Render dossier |
| `GET` | `/api/reports/versions/{id}/exports` | List exports |

### Entities API (`/api/entities`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/entities/merge` | Merge two entities |
| `POST` | `/api/entities/unmerge` | Reverse a merge |

### Exports API (`/api/exports`)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/exports/{id}` | Get export (JSON or HTML) |
| `GET` | `/api/exports/by-version/{id}` | List exports (alias) |

---

## Collections & Indexes Inventory

### Collections (24 total)

| Collection | Purpose | Key Indexes |
|------------|---------|-------------|
| `permits` | Permit data | `city`, `status`, `source_permit_id` |
| `permit_sources` | Data sources | `permit_id` |
| `permit_events` | Audit trail | `permit_id`, `created_at` |
| `reports` | Report metadata | `permit_id`, `status` |
| `report_versions` | Immutable snapshots | `report_id`, `version` |
| `report_events` | Audit trail | `report_id` |
| `stage_attempts` | Pipeline runs | `report_version_id`, `stage_name`, `idempotency_key` (unique) |
| `stage_outputs` | Stage results | `stage_attempt_id` |
| `stage_events` | Audit trail | `stage_attempt_id` |
| `evidence_items` | Raw evidence | `item_type` |
| `evidence_links` | Link evidence | `link_type`, `link_id` |
| `derived_claims` | AI claims | `evidence_id` |
| `entities` | Resolved entities | `canonical_name`, `status` |
| `entity_aliases` | Name aliases | `entity_id`, `alias_norm` |
| `entity_identifiers` | IDs (EIN, etc) | `entity_id`, `identifier_type` |
| `entity_links` | Relationships | `from_entity_id`, `to_entity_id` |
| `entity_match_suggestions` | Review queue | `report_version_id`, `status`, `alias_norm` |
| `merge_ledger` | Merge history | `winner_entity_id`, `merged_entity_id` |
| `unmerge_ledger` | Unmerge history | `merge_ledger_id` |
| `operator_locks` | Lock flags | `target_type`, `target_id` |
| `exports` | Export records | `report_version_id` + `export_type` + `template_version` (unique) |
| `export_events` | Audit trail | `export_id` |
| `report_outcomes` | Final outcomes | `report_id` |
| `comparables` | Market comps | `entity_id` |

---

## Operator Happy Path

### Step-by-Step Workflow

1. **Open App**
   - Navigate to `https://<app>.preview.emergentagent.com`
   - See permits list (11 seeded permits)

2. **Select Permit**
   - Click any permit row (e.g., "500 W Madison St")
   - See permit detail with info card

3. **Create Report** (if needed)
   - Click "Create Report" button
   - See Report ID appear

4. **Create Version** (if needed)
   - Click "Create New Version" button
   - See "Current Version: v1 • queued"
   - Tabs appear: Pipeline, Entities, Exports, Preview

5. **Run Scope Summary**
   - On Pipeline tab, note auto-generated idempotency key
   - Click "Run" button
   - See green banner: "✓ New scope_summary completed"
   - See stage attempt in list with "succeeded" badge

6. **Extract Entities** (optional)
   - Click "Entities" tab
   - Click "Extract Entities" button
   - See suggestions in review queue

7. **Export Dossier**
   - Click "Exports" tab
   - Click "Render" button
   - See green banner: "✓ New dossier exported"
   - Export appears in list with "ready" status

8. **Preview Dossier**
   - Click "Preview" tab (or click "Preview" on export)
   - See full HTML dossier in iframe

---

## Idempotency Guidance

### Scope Summary

**Key:** `(report_version_id, stage_name, idempotency_key)` unique index

```bash
# First run - creates new attempt
POST /api/reports/versions/{id}/stages/scope_summary/run
{"idempotency_key": "run-001"}
→ {"is_rerun": false, "attempt": {...}}

# Second run with same key - returns existing
POST /api/reports/versions/{id}/stages/scope_summary/run
{"idempotency_key": "run-001"}
→ {"is_rerun": true, "attempt": {...}}  # Same attempt_id
```

### Export Render

**Key:** `(report_version_id, export_type, template_version)` unique index

```bash
# First render - creates new export
POST /api/reports/versions/{id}/exports/dossier/render
{"template_version": "v1"}
→ {"is_rerun": false, "export": {...}}

# Second render - returns existing
POST /api/reports/versions/{id}/exports/dossier/render
{"template_version": "v1"}
→ {"is_rerun": true, "export": {...}}  # Same export_id
```

### UI Feedback

| Result | Banner Color | Message |
|--------|--------------|---------|
| New | Green | "✓ New scope_summary completed" |
| Reused | Amber | "↩ Reused existing result (idempotent)" |

---

## Known Limitations

1. **Deterministic Pipeline** - `scope_summary` uses rule-based logic, not real LLM
2. **No PDF Export** - HTML only (PDF is future enhancement)
3. **Single Template** - Only `v1` template supported
4. **No Auth** - Single-tenant, no user authentication
5. **No Real OSINT** - No external data enrichment yet
6. **Entity Merge UI** - Read-only review queue (merge via API only)

---

## Next Steps (Post-RC)

| Priority | Feature |
|----------|---------|
| P1 | Additional pipeline stages |
| P1 | Real LLM integration |
| P1 | PDF dossier generation |
| P2 | External OSINT integration |
| P2 | Multi-operator support |
| P2 | Expanded seed data (20-50 permits) |

---

## Testing

### Backend Tests

```bash
cd /app/backend && python -m pytest -q
```

**Expected Output:**
```
........................................                                 [100%]
40 passed in X.XXs
```

### Frontend Lint

```bash
cd /app/frontend && npx eslint src/ --ext .js,.jsx
```

**Expected Output:** No errors

### Smoke Test

```bash
bash /app/backend/scripts/smoke_mvp.sh
```

**Expected Output:**
- All steps complete
- Export status = "ready"
- HTML contains "Permit Intelligence Dossier"

---

## Smoke Test Checklist

| # | Step | Expected |
|---|------|----------|
| 1 | Seed permits | `seeded_count >= 0` (idempotent) |
| 2 | Create report | `report_id` returned |
| 3 | Create version | `version_id` returned |
| 4 | Run scope_summary | `status: succeeded` |
| 5 | Render export | `status: ready` |
| 6 | Verify HTML | Contains "Permit Intelligence Dossier" |
| 7 | Idempotency rerun | `is_rerun: true` |

---

## Quick Links

- [Milestone 1](./MILESTONE-1-COMPLETE.md) - Data Model
- [Milestone 2](./MILESTONE-2-COMPLETE.md) - State Machines
- [Milestone 3](./MILESTONE-3-COMPLETE.md) - Pipeline Skeleton
- [Milestone 4](./MILESTONE-4-COMPLETE.md) - Entity Resolution
- [Milestone 5](./MILESTONE-5-COMPLETE.md) - Export Dossier
- [Milestone 6](./MILESTONE-6-COMPLETE.md) - Operator UI
