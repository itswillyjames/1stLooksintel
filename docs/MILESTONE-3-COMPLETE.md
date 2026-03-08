# Milestone 3: Pipeline Skeleton + 1 Real Stage — COMPLETE ✓

**Completed:** 2026-03-08
**Status:** All acceptance criteria met

---

## Quick Links

- **Preview URL**: `https://intel-scope-1.preview.emergentagent.com`
- **Test Command**: `cd /app/backend && python -m pytest tests/test_pipeline.py -v`
- **Pipeline Module**: `/app/backend/app/pipeline/`
  - `stage_runner.py` — Base stage interface
  - `orchestrator.py` — Stage execution orchestrator
  - `stages/scope_summary.py` — Deterministic scope_summary stage

---

## What Was Delivered

### 1. Pipeline Infrastructure (`/app/backend/app/pipeline/`)

#### Base Stage Runner (`stage_runner.py`)
Abstract interface for all pipeline stages:
```python
class StageRunner(ABC):
    @property
    @abstractmethod
    def stage_name(self) -> str
    
    @property
    @abstractmethod
    def input_model(self) -> type[BaseModel]  # Pydantic validation
    
    @property
    @abstractmethod
    def output_model(self) -> type[BaseModel]  # Pydantic validation
    
    @abstractmethod
    def execute(self, input_data: Dict) -> Dict  # Deterministic logic
    
    def validate_semantic(self, output: BaseModel) -> Tuple[bool, str]  # Custom rules
    
    def run(self, input_data: Dict) -> Dict  # Complete pipeline
```

**Key features:**
- Input validation (Pydantic)
- Output validation (Pydantic + semantic)
- Pluggable semantic validation
- Clean separation of concerns

#### Orchestrator (`orchestrator.py`)
Manages stage execution lifecycle:
- **Idempotency**: Unique constraint on `(report_version_id, stage_name, idempotency_key)`
- **State machine integration**: `queued` → `running` → `succeeded`/`failed`
- **Event emission**: Emits `stage_events` for all transitions
- **Metrics tracking**: Latency, output size, timestamps
- **Error handling**: Captures exception class + message

### 2. Scope Summary Stage (`stages/scope_summary.py`)

**Deterministic implementation** (no LLM calls):

#### Input Model
```python
class ScopeSummaryInput(BaseModel):
    permit_id: str
    city: str
    address_raw: str
    work_type: str
    description_raw: str
    valuation: int
    filed_date: str
    issued_date: str | None
```

#### Output Model
```python
class ScopeSummaryOutput(BaseModel):
    project_type: str  # commercial|mixed_use|industrial|institutional|residential|other
    scope_summary: str  # 10-500 chars
    estimated_size_sqft: int  # >= 0
    buyer_fit: BuyerFit  # score: 0-100, reasons: List[str]
```

#### Logic (Rule-Based)
1. **Project type classification**: Keyword matching on `work_type` and `description`
2. **Scope summary generation**: Template-based text from permit data
3. **Size estimation**: Valuation ÷ cost-per-sqft (by project type)
4. **Buyer fit scoring**: Deterministic rules based on:
   - Valuation (high/mid/low)
   - Project type (target sectors)
   - Keywords (new construction, expansion, etc.)

#### Semantic Validation
- Buyer fit score: 0-100
- Buyer fit reasons: At least 1
- Scope summary: Not placeholder text, 10-500 chars
- Estimated size: > 0 and < 10M sqft

### 3. API Endpoints

#### POST /api/pipeline/report_versions/{version_id}/stages/scope_summary/run
Run the scope_summary stage for a report version.

**Request:**
```json
{
  "idempotency_key": "optional-custom-key"
}
```

**Response:**
```json
{
  "attempt": {
    "id": "uuid",
    "report_version_id": "uuid",
    "stage_name": "scope_summary",
    "status": "succeeded",
    "idempotency_key": "...",
    "provider": "deterministic",
    "model_id": "rule-based",
    "attempt_no": 1,
    "started_at": "2026-03-08T19:00:00Z",
    "finished_at": "2026-03-08T19:00:00.003Z",
    "metrics": {
      "latency_ms": 3,
      "output_size_bytes": 367
    }
  },
  "output": {
    "id": "uuid",
    "stage_attempt_id": "uuid",
    "output": {
      "project_type": "commercial",
      "scope_summary": "Commercial project at 500 W Madison St...",
      "estimated_size_sqft": 12500,
      "buyer_fit": {
        "score": 100.0,
        "reasons": ["High-value project: $2.5M", "Target sector: commercial"]
      }
    },
    "output_hash": "sha256-hash"
  },
  "is_rerun": false
}
```

#### GET /api/pipeline/stage_attempts/{attempt_id}
Retrieve a stage attempt by ID, including its output.

**Response:**
```json
{
  "attempt": { /* same as above */ },
  "output": { /* same as above */ }
}
```

### 4. Idempotency Enforcement

**Unique Index:** `(report_version_id, stage_name, idempotency_key)`

**Behavior:**
- First run: Creates new attempt + output, executes stage
- Rerun with same key: Returns existing attempt + output, **no re-execution**

**Idempotency Key Generation:**
```python
# Custom key (if provided)
idempotency_key = request.idempotency_key

# Auto-generated (if not provided)
idempotency_key = sha256(f"{version_id}:{stage_name}:{input_hash}")
```

### 5. State Machine Integration

**Stage Attempt States:**
```
queued → running → succeeded
                 ↘ failed
```

**Transitions:**
- `queued → running`: When execution starts
- `running → succeeded`: When output validated successfully
- `running → failed`: When validation or execution fails

**Event Emission:**
All transitions emit `stage_events`:
```json
{
  "_id": "uuid",
  "stage_attempt_id": "uuid",
  "event_type": "status_changed",
  "event_payload": {
    "from_status": "running",
    "to_status": "succeeded",
    "reason": "Stage execution completed successfully"
  },
  "created_at": "2026-03-08T19:00:00Z"
}
```

### 6. Automated Tests

**9 tests, all passing:**

#### Test Coverage:
1. ✅ Stage properties (name, input_model, output_model)
2. ✅ Project type classification (deterministic rules)
3. ✅ Scope summary generation
4. ✅ Buyer fit scoring
5. ✅ Semantic validation (valid + invalid cases)
6. ✅ Stage execution success (attempt + output + events created)
7. ✅ Idempotent rerun (returns same attempt/output)
8. ✅ Input validation failure (catches missing fields)
9. ✅ Semantic validation failure (catches invalid output)

**Test Results:**
```bash
cd /app/backend
python -m pytest tests/test_pipeline.py -v

============================== 9 passed in 0.64s ===============================
```

---

## Files Created

### Pipeline Module:
1. `/app/backend/app/pipeline/__init__.py`
2. `/app/backend/app/pipeline/stage_runner.py` — Base stage interface
3. `/app/backend/app/pipeline/orchestrator.py` — Execution orchestrator
4. `/app/backend/app/pipeline/stages/__init__.py`
5. `/app/backend/app/pipeline/stages/scope_summary.py` — Deterministic stage

### API:
6. `/app/backend/app/api/pipeline.py` — Pipeline endpoints

### Tests:
7. `/app/backend/tests/test_pipeline.py` — Pipeline + stage tests

### Modified:
8. `/app/backend/server.py` — Added pipeline router

---

## Verification Results

### Test Suite: 9/9 Pass ✅
```bash
cd /app/backend
python -m pytest tests/test_pipeline.py -v

tests/test_pipeline.py::TestScopeSummaryStage::test_stage_properties PASSED
tests/test_pipeline.py::TestScopeSummaryStage::test_project_type_classification PASSED
tests/test_pipeline.py::TestScopeSummaryStage::test_scope_summary_generation PASSED
tests/test_pipeline.py::TestScopeSummaryStage::test_buyer_fit_scoring PASSED
tests/test_pipeline.py::TestScopeSummaryStage::test_semantic_validation PASSED
tests/test_pipeline.py::TestPipelineOrchestration::test_stage_execution_success PASSED
tests/test_pipeline.py::TestPipelineOrchestration::test_idempotent_rerun PASSED
tests/test_pipeline.py::TestPipelineOrchestration::test_input_validation_failure PASSED
tests/test_pipeline.py::TestPipelineOrchestration::test_semantic_validation_failure PASSED

============================== 9 passed in 0.64s ===============================
```

### Manual API Verification ✅

#### 1. Stage Execution
```bash
curl -X POST /api/pipeline/report_versions/{version_id}/stages/scope_summary/run \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key": "test-1"}'

Response:
{
  "attempt": {
    "id": "31132ecb-1c29-4d4c-b528-1cb59b6a36d8",
    "status": "succeeded",
    "stage_name": "scope_summary",
    "metrics": {"latency_ms": 3, "output_size_bytes": 367}
  },
  "output": {
    "output": {
      "project_type": "commercial",
      "scope_summary": "Commercial project at 500 W Madison St...",
      "estimated_size_sqft": 12500,
      "buyer_fit": {"score": 100.0, "reasons": [...]}
    }
  },
  "is_rerun": false
}
```

#### 2. Idempotent Rerun
```bash
curl -X POST /api/pipeline/report_versions/{version_id}/stages/scope_summary/run \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key": "test-1"}'  # Same key

Response:
{
  "attempt": {"id": "31132ecb-1c29-4d4c-b528-1cb59b6a36d8"},  # Same ID
  "is_rerun": true  # ✅ Idempotency enforced
}
```

#### 3. Event Emission Verified
```python
db.stage_events.find({"stage_attempt_id": "31132ecb-..."})

Results:
- queued → running
- running → succeeded
```

---

## Acceptance Checklist

- [x] NO UI generated (backend only)
- [x] Exactly ONE stage implemented: `scope_summary`
- [x] Deterministic implementation (no LLM calls)
- [x] Strict validation: Pydantic models + semantic validation
- [x] Idempotency enforced: unique on `(report_version_id, stage_name, idempotency_key)`
- [x] Rerun with same key returns existing attempt/output
- [x] State machine integrated: `queued → running → succeeded/failed`
- [x] Event emission for all transitions
- [x] API endpoints: `POST .../stages/scope_summary/run`, `GET .../stage_attempts/{id}`
- [x] Tests: 9/9 passing (success, idempotency, validation, events)
- [x] No new status enums added (used existing from Milestone 2)

---

## Design Decisions

### 1. Deterministic Stage Implementation
**Reason:** Milestone 3 focuses on pipeline infrastructure, not AI integration.
- Rule-based classification (keywords)
- Template-based text generation
- Deterministic scoring formulas
- No external API calls → fast, reliable, testable

### 2. Idempotency Key Strategy
**Auto-generated:** `sha256(version_id + stage_name + input_hash)`
**Custom:** User can provide their own key for manual control
**Rationale:** Supports both automatic deduplication and explicit retry control

### 3. Input Hash Computation
Uses sorted JSON to ensure stable hashing across equivalent inputs.
```python
input_hash = sha256(json.dumps(input_data, sort_keys=True))
```

### 4. Semantic Validation Separation
Pydantic handles JSON schema (types, ranges, patterns).
`validate_semantic()` handles business rules (e.g., "no placeholder text").
**Rationale:** Clear separation of concerns, easier to extend per-stage logic.

### 5. Event Emission on Every Transition
Even `queued → running` emits an event.
**Rationale:** Complete audit trail for debugging and observability.

### 6. Metrics Collection
- `latency_ms`: Stage execution time
- `output_size_bytes`: Size of JSON output
- `input_tokens`, `output_tokens`: Reserved for LLM stages (Milestone 4+)

---

## Example: Scope Summary Output

**Input:** Commercial permit, $2.5M valuation, "new construction"

**Output:**
```json
{
  "project_type": "commercial",
  "scope_summary": "Commercial project at 500 W Madison St involving new construction of 12-story mixed-use building with retail and office space ($2.5M project value).",
  "estimated_size_sqft": 12500,
  "buyer_fit": {
    "score": 100.0,
    "reasons": [
      "High-value project: $2.5M",
      "Target sector: commercial",
      "Key activities: new construction, tenant improvement"
    ]
  }
}
```

---

## Usage Examples

### Run Stage (First Time)
```bash
API_URL="https://intel-scope-1.preview.emergentagent.com"

# Get report version ID
VERSION_ID="..."

# Run scope_summary stage
curl -X POST "$API_URL/api/pipeline/report_versions/$VERSION_ID/stages/scope_summary/run" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key": "run-1"}' | jq .

# Returns: attempt (succeeded) + output + is_rerun: false
```

### Idempotent Rerun
```bash
# Run again with same key
curl -X POST "$API_URL/api/pipeline/report_versions/$VERSION_ID/stages/scope_summary/run" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key": "run-1"}' | jq .

# Returns: same attempt + output + is_rerun: true
```

### Get Stage Attempt
```bash
ATTEMPT_ID="31132ecb-1c29-4d4c-b528-1cb59b6a36d8"

curl "$API_URL/api/pipeline/stage_attempts/$ATTEMPT_ID" | jq .

# Returns: attempt + output (if succeeded)
```

### Query Events
```bash
mongo test_database --eval "
  db.stage_events.find({stage_attempt_id: '$ATTEMPT_ID'}).forEach(printjson)
"

# Shows: queued→running, running→succeeded events
```

---

## Next Steps

### Milestone 4: Entity Resolution + Merge/Unmerge
- Implement entity extraction from stage outputs
- Entity graph creation
- Match tiers (exact, fuzzy, suggested)
- Merge ledger with lineage
- Unmerge capability
- Review queue for operator confirmation

### Milestone 5: Export HTML Dossier
- Template versioning
- HTML renderer with permit data + stage outputs
- Export manifest JSON
- PDF derivation (optional)

### Milestone 6: Operator UI
- Permit list + filters
- Report run controls
- Stage status visualization
- Entity review screens
- Merge/unmerge UI
- Export download

---

**Milestone 3 Status: COMPLETE ✓**

Pipeline infrastructure implemented. One deterministic stage (`scope_summary`) working end-to-end with validation, idempotency, and event emission.
