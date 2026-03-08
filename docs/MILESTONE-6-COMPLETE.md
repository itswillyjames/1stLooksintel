# MILESTONE 6: Operator UI Flows

**Status:** COMPLETE  
**Date:** 2025-01-XX  
**Backend Tests:** 40/40 passing  
**Frontend Lint:** No issues

## Milestone 6.1 Patch: State Persistence

**Date:** 2025-01-XX

### Changes

1. **No auto-creation of versions on navigation**
   - Previously: Navigating to a permit would create a new version each time
   - Now: Uses existing `report.active_version_id` when returning to a permit

2. **Load existing report on mount**
   - New API endpoint: `GET /api/reports/by-permit/{permit_id}`
   - On permit detail load, fetches existing report (if any) instead of requiring creation

3. **Current Version display**
   - Shows "Current Version" box with version number, status, and ID
   - Clear CTA when no version exists: "No active version. Click Create New Version..."

4. **Export selection state persists across tabs**
   - Selected export is highlighted with checkmark and blue border
   - Preview auto-loads the first ready export when version is loaded
   - Switching tabs preserves the selected export preview

### Backend Change (minimal)

Added one read-only endpoint:
```
GET /api/reports/by-permit/{permit_id}
```
Returns existing report for permit, or 404 if none exists.

---


---

## Summary

Milestone 6 implements the operator UI for the permit intelligence workbench. The UI provides a complete workflow for:
- Browsing and filtering permits
- Creating reports and versions
- Running pipeline stages (scope_summary)
- Reviewing entity suggestions
- Exporting and previewing HTML dossiers

---

## UI Features

### Permits List
- **Filters:** City dropdown, status dropdown, minimum score input
- **Seed Button:** One-click seeding of sample permits
- **Sortable Table:** Address, city, status, score, valuation
- **Click to View:** Click any permit row to open detail view

### Permit Detail View
- **Permit Info Card:** Work type, valuation, status, score, description, owner, contractor
- **Report Actions:** Create Report → Create Version
- **Tabbed Interface:** Pipeline, Entities, Exports, Preview

### Pipeline Tab
- **Run Scope Summary:** Execute with custom idempotency key
- **Stage Attempts List:** Shows all attempts with status icons
- **Attempt Detail:** Click to view full attempt JSON and output

### Entities Tab
- **Extract Entities:** Run entity extraction from permit data
- **Match Suggestions:** Read-only review queue showing name, role, match type, status

### Exports Tab
- **Render Dossier:** Export HTML with custom idempotency key
- **Exports List:** Shows all exports with status, template version, timestamp
- **Preview Button:** Load HTML into preview iframe

### Preview Tab
- **Dossier Preview:** Full HTML dossier rendered in iframe

---

## Idempotency UX

When an operation returns a cached/reused result:

| Action | New Result | Reused Result |
|--------|------------|---------------|
| Run Scope Summary | Green banner: "✓ New scope_summary completed" | Amber banner: "↩ Reused existing scope_summary result (idempotent)" |
| Render Export | Green banner: "✓ New dossier exported" | Amber banner: "↩ Reused existing export (idempotent)" |
| Toast | "Stage completed" / "Dossier exported" | "Reused existing result" |

---

## Error UX

- **Toast Summary:** Shows brief error message at top-right
- **Error Panel:** Expandable panel with:
  - Error summary header
  - "Show Details" button to reveal full JSON
  - Collapsible JSON view with syntax highlighting
  - "Dismiss" button to clear error

---

## Routes Used (Canonical)

| Method | Path | UI Action |
|--------|------|-----------|
| `GET` | `/api/permits` | Permits list with filters |
| `POST` | `/api/permits/seed` | Seed button |
| `GET` | `/api/permits/{id}` | Permit detail |
| `POST` | `/api/reports` | Create Report button |
| `GET` | `/api/reports/{id}` | Load report info |
| `POST` | `/api/reports/{id}/versions` | Create Version button |
| `GET` | `/api/reports/versions/{id}` | Load version info |
| `POST` | `/api/reports/versions/{id}/stages/scope_summary/run` | Run Scope Summary |
| `GET` | `/api/reports/versions/{id}/stage_attempts` | Stage Attempts list |
| `GET` | `/api/reports/stage_attempts/{id}` | Attempt detail |
| `POST` | `/api/reports/versions/{id}/entities/extract` | Extract Entities |
| `GET` | `/api/reports/versions/{id}/entity_suggestions` | Suggestions list |
| `POST` | `/api/reports/versions/{id}/exports/dossier/render` | Render Dossier |
| `GET` | `/api/reports/versions/{id}/exports` | Exports list |
| `GET` | `/api/exports/{id}?format=html` | Preview HTML |

---

## Operator Happy Path

### Step-by-Step Workflow

1. **Open App**
   - Navigate to `https://intel-scope-1.preview.emergentagent.com`
   - See permits list with 11 sample permits

2. **Filter Permits (Optional)**
   - Use "All Cities" dropdown to filter by city (e.g., Chicago)
   - Use "All Statuses" dropdown to filter by status (e.g., shortlisted)
   - Enter minimum score in "Min Score" input

3. **Select a Permit**
   - Click on any permit row (e.g., "500 W Madison St")
   - See permit detail view with all information

4. **Create Report**
   - Click "Create Report" button
   - See green banner: "Report created successfully"

5. **Create Version**
   - Click "Create Version" button
   - See green banner: "Version created with permit snapshot"
   - See tabs appear: Pipeline, Entities, Exports, Preview

6. **Run Scope Summary**
   - On Pipeline tab, see auto-generated idempotency key
   - Click "Run" button
   - See green banner: "✓ New scope_summary completed"
   - See stage attempt in list with "succeeded" badge

7. **View Stage Output**
   - Click on the scope_summary attempt row
   - See expanded detail with full JSON output

8. **Extract Entities**
   - Click "Entities" tab
   - Click "Extract Entities" button
   - See green banner: "Entities extracted"

9. **Review Suggestions**
   - Scroll down to see "Match Suggestions" table
   - View extracted entities with match type and confidence

10. **Export Dossier**
    - Click "Exports" tab
    - See auto-generated idempotency key
    - Click "Render" button
    - See green banner: "✓ New dossier exported"
    - See export in list with "ready" status

11. **Preview Dossier**
    - Click "Preview" button on the export row
    - Click "Preview" tab
    - See full HTML dossier in iframe

12. **Test Idempotency**
    - On Pipeline or Exports tab, click Run/Render again
    - See amber banner: "↩ Reused existing result (idempotent)"

---

## Files Created

### Frontend Components
- `/app/frontend/src/lib/api.js` - API client with all endpoints
- `/app/frontend/src/hooks/useApiCall.js` - API call hook with error handling
- `/app/frontend/src/components/ErrorPanel.jsx` - Collapsible error display
- `/app/frontend/src/components/PermitsList.jsx` - Permits list with filters
- `/app/frontend/src/components/PermitDetail.jsx` - Full permit workflow UI

### Modified Files
- `/app/frontend/src/App.js` - Main app with routing
- `/app/frontend/src/components/ui/sonner.jsx` - Fixed for CRA (removed next-themes)

---

## Verification Steps

### 1. Permits List
```
1. Open https://intel-scope-1.preview.emergentagent.com
2. Verify 11 permits are displayed
3. Use city filter → verify list updates
4. Use status filter → verify list updates
5. Enter min score → verify list updates
6. Click "Clear" → verify filters reset
```

### 2. Seed Button
```
1. Click "Seed" button
2. Verify toast: "Permits seeded successfully"
3. Verify list refreshes (idempotent - no duplicates)
```

### 3. Create Report + Version
```
1. Click any permit row
2. Click "Create Report"
3. Verify Report ID appears
4. Click "Create Version"
5. Verify version badge "v1 • queued"
6. Verify tabs appear
```

### 4. Run Scope Summary
```
1. On Pipeline tab, note idempotency key
2. Click "Run"
3. Verify green banner: "New scope_summary completed"
4. Verify stage attempt appears with "succeeded"
5. Click Run again
6. Verify amber banner: "Reused existing result"
```

### 5. Entity Extraction
```
1. Click "Entities" tab
2. Click "Extract Entities"
3. Verify banner: "Entities extracted"
4. Scroll to see suggestions table
```

### 6. Export + Preview
```
1. Click "Exports" tab
2. Note idempotency key
3. Click "Render"
4. Verify green banner: "New dossier exported"
5. Verify export appears in list with "ready" status
6. Click "Preview" button on export
7. Click "Preview" tab
8. Verify HTML dossier in iframe
```

### 7. Error Handling
```
1. Attempt invalid operation (e.g., bad version ID)
2. Verify error toast appears
3. Verify error panel shows
4. Click "Show Details"
5. Verify full JSON error visible
6. Click "Dismiss"
```

---

## Test IDs

All interactive elements have `data-testid` attributes for testing:

| Element | Test ID |
|---------|---------|
| Permits list card | `permits-list-card` |
| Refresh permits | `refresh-permits-btn` |
| Seed button | `seed-permits-btn` |
| Filter city | `filter-city` |
| Filter status | `filter-status` |
| Filter min score | `filter-min-score` |
| Clear filters | `clear-filters-btn` |
| Permit row | `permit-row-{id}` |
| Back button | `back-to-list-btn` |
| Create report | `create-report-btn` |
| Create version | `create-version-btn` |
| Tab: Pipeline | `tab-pipeline` |
| Tab: Entities | `tab-entities` |
| Tab: Exports | `tab-exports` |
| Tab: Preview | `tab-preview` |
| Scope idempotency | `scope-idempotency-input` |
| Run scope | `run-scope-btn` |
| Extract entities | `extract-entities-btn` |
| Export idempotency | `export-idempotency-input` |
| Render export | `render-export-btn` |
| Preview button | `preview-export-btn-{id}` |
| Dossier iframe | `dossier-preview-iframe` |

---

## Quick Links

- [Milestone 1](./MILESTONE-1-COMPLETE.md) - Data Model + Persistence
- [Milestone 2](./MILESTONE-2-COMPLETE.md) - State Machines
- [Milestone 2.1](./MILESTONE-2_1-COMPLETE.md) - Documentation Patch
- [Milestone 3](./MILESTONE-3-COMPLETE.md) - Pipeline Skeleton
- [Milestone 4](./MILESTONE-4-COMPLETE.md) - Entity Resolution
- [Milestone 5](./MILESTONE-5-COMPLETE.md) - Export HTML Dossier
- [Design Doc](./milestone-1-design.md) - Original specifications
