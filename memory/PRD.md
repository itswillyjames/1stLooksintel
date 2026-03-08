# Permit Intel - Product Requirements Document

## Overview

**Product:** Permit Intel - Single-tenant, solo-operator permit intelligence workbench

**Stack:** React + TypeScript (frontend), FastAPI (backend), MongoDB (database)

**Protocol:** Milestone-by-milestone development with small, testable diffs

---

## Core Workflow

1. **Ingest permits** - Import permit data from various sources
2. **Prequalification scoring** - Score permits based on fit criteria
3. **Pipeline enrichment** - Run staged data enrichment (scope_summary, etc.)
4. **Entity resolution** - Extract, merge, and manage entities
5. **Export dossiers** - Generate HTML dossiers with manifests

---

## Milestone Status

| # | Milestone | Status | Tests | Doc |
|---|-----------|--------|-------|-----|
| 1 | Data Model + Persistence + Seed | ✅ COMPLETE | Pass | [MILESTONE-1-COMPLETE.md](/app/docs/MILESTONE-1-COMPLETE.md) |
| 2 | Canonical State Machines | ✅ COMPLETE | Pass | [MILESTONE-2-COMPLETE.md](/app/docs/MILESTONE-2-COMPLETE.md) |
| 2.1 | Documentation Patch | ✅ COMPLETE | Pass | [MILESTONE-2_1-COMPLETE.md](/app/docs/MILESTONE-2_1-COMPLETE.md) |
| 3 | Pipeline Skeleton (scope_summary) | ✅ COMPLETE | Pass | [MILESTONE-3-COMPLETE.md](/app/docs/MILESTONE-3-COMPLETE.md) |
| 4 | Entity Resolution + Merge/Unmerge | ✅ COMPLETE | Pass | [MILESTONE-4-COMPLETE.md](/app/docs/MILESTONE-4-COMPLETE.md) |
| 5 | Export HTML Dossier + Manifest | ✅ COMPLETE | Pass | [MILESTONE-5-COMPLETE.md](/app/docs/MILESTONE-5-COMPLETE.md) |
| 6 | Operator UI Flows | ✅ COMPLETE | Pass | [MILESTONE-6-COMPLETE.md](/app/docs/MILESTONE-6-COMPLETE.md) |

---

## What's Been Implemented

### Collections (24 total)
- `permits`, `permit_sources`, `permit_events`
- `reports`, `report_versions`, `report_events`
- `stage_attempts`, `stage_outputs`, `stage_events`
- `evidence_items`, `evidence_links`, `derived_claims`
- `entities`, `entity_aliases`, `entity_identifiers`, `entity_links`
- `merge_ledger`, `unmerge_ledger`
- `operator_locks`
- `exports`, `export_events`
- `report_outcomes`, `comparables`
- `entity_match_suggestions`

### State Machines
- PermitStatus: new → normalized → prequalified → shortlisted/rejected → archived
- ReportStatus: draft → queued → running → partial/completed/failed → superseded → archived
- ReportVersionStatus: queued → running → partial/completed/failed
- StageAttemptStatus: queued → running → succeeded/failed
- ExportStatus: draft → rendering → ready → delivered/failed

### API Endpoints
- `/api/permits/*` - Permit CRUD and seeding
- `/api/reports/*` - Report management and status transitions
- `/api/reports/versions/*` - Report version management
- `/api/reports/versions/{id}/stages/scope_summary/run` - Pipeline execution
- `/api/reports/versions/{id}/entities/extract` - Entity extraction
- `/api/reports/versions/{id}/exports/dossier/render` - Dossier export
- `/api/entities/merge`, `/api/entities/unmerge` - Entity merge/unmerge
- `/api/exports/*` - Export retrieval

### Key Features
- Idempotent seeding with 11 sample permits
- State machine validation with event emission
- Pipeline orchestration with idempotency (scope_summary stage)
- Entity extraction, canonicalization, and fuzzy matching
- Merge/unmerge with full ledger audit trail
- HTML dossier export with manifest JSON
- Deterministic output for reproducibility

---

## Prioritized Backlog

### P0 - Critical Path
- ✅ All core milestones complete (1-6)

### P1 - Important
- Additional pipeline stages (beyond scope_summary)
- Real LLM integration (replace deterministic logic)
- PDF dossier generation

### P2 - Nice to Have
- External OSINT browsing/scraping
- Expanded seed data (20-50 permits)
- Multi-operator support
- Notification system
- State persistence across navigation (report/version retention)

---

## Architecture

```
/app/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI routers
│   │   ├── db/            # MongoDB connection, collections, seed
│   │   ├── entities/      # Entity resolution logic
│   │   ├── models/        # Pydantic models
│   │   ├── pipeline/      # Orchestrator and stages
│   │   ├── services/      # Business logic
│   │   └── state_machine/ # Status enums and validators
│   ├── tests/             # Pytest test suites
│   └── server.py          # FastAPI app entry
├── docs/                  # Milestone documentation
├── frontend/              # React app (untouched)
└── memory/                # PRD and tracking docs
```

---

## Test Coverage

- **test_state_machines.py** - State transition validation
- **test_pipeline.py** - Pipeline orchestration and idempotency
- **test_entities.py** - Entity extraction, merge, unmerge
- **test_exports.py** - HTML rendering, manifest, idempotency

**Current:** 40 tests, all passing

---

## Next Steps

1. Complete Milestone 6: Operator UI Flows
2. Integrate additional pipeline stages
3. Add real LLM capabilities
