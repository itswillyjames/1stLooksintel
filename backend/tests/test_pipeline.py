"""Tests for pipeline execution and idempotency.

Tests:
1. Stage execution creates attempt + output + events
2. Idempotent rerun returns same attempt/output
3. Input validation enforced
4. Output validation (JSON + semantic) enforced
5. State machine transitions enforced
"""

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
import uuid

from app.pipeline.stages import ScopeSummaryStage
from app.pipeline import run_stage

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
    await test_db.stage_attempts.delete_many({})
    await test_db.stage_outputs.delete_many({})
    await test_db.stage_events.delete_many({})
    
    yield test_db
    
    # Clean up after tests
    await test_db.report_versions.delete_many({})
    await test_db.stage_attempts.delete_many({})
    await test_db.stage_outputs.delete_many({})
    await test_db.stage_events.delete_many({})
    
    client.close()


@pytest_asyncio.fixture
async def test_report_version(db):
    """Create a test report version with permit data."""
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
                "address_raw": "123 Test St",
                "work_type": "commercial_new_construction",
                "description_raw": "New construction of 5-story mixed-use building with retail and office space",
                "valuation": 2500000,
                "filed_date": "2024-01-15T00:00:00Z",
                "issued_date": "2024-02-01T00:00:00Z"
            }
        },
        "status": "queued",
        "created_at": now,
        "updated_at": now
    }
    
    await db.report_versions.insert_one(version_doc)
    return version_id


class TestScopeSummaryStage:
    """Test scope_summary stage implementation."""
    
    def test_stage_properties(self):
        """Test stage has correct properties."""
        stage = ScopeSummaryStage()
        assert stage.stage_name == "scope_summary"
        assert stage.input_model is not None
        assert stage.output_model is not None
    
    def test_project_type_classification(self):
        """Test deterministic project type classification."""
        stage = ScopeSummaryStage()
        
        assert stage.classify_project_type("commercial_retail", "retail store") == "commercial"
        assert stage.classify_project_type("industrial_warehouse", "warehouse") == "industrial"
        assert stage.classify_project_type("institutional_school", "school renovation") == "institutional"
        assert stage.classify_project_type("residential_apartment", "apartment building") == "residential"
        assert stage.classify_project_type("mixed_use", "residential and commercial") == "mixed_use"
    
    def test_scope_summary_generation(self):
        """Test scope summary text generation."""
        stage = ScopeSummaryStage()
        
        summary = stage.generate_scope_summary(
            work_type="commercial_new_construction",
            description="New 5-story office building with ground floor retail",
            valuation=2500000,
            address="123 Main St"
        )
        
        assert "commercial" in summary.lower()
        assert "123 Main St" in summary
        assert "$2.5M" in summary or "$2500" in summary
    
    def test_buyer_fit_scoring(self):
        """Test buyer fit scoring logic."""
        stage = ScopeSummaryStage()
        
        # High-value commercial project
        buyer_fit = stage.score_buyer_fit(
            valuation=2500000,
            project_type="commercial",
            description="New construction of office building with tenant improvements"
        )
        
        assert buyer_fit.score >= 70
        assert len(buyer_fit.reasons) > 0
        assert any("value" in reason.lower() for reason in buyer_fit.reasons)
    
    def test_semantic_validation(self):
        """Test semantic validation rules."""
        stage = ScopeSummaryStage()
        
        from app.pipeline.stages.scope_summary import ScopeSummaryOutput, BuyerFit
        
        # Valid output
        valid_output = ScopeSummaryOutput(
            project_type="commercial",
            scope_summary="Commercial project at 123 Main St involving new construction ($2.5M project value).",
            estimated_size_sqft=12500,
            buyer_fit=BuyerFit(score=85.0, reasons=["High-value project: $2.5M"])
        )
        
        is_valid, reason = stage.validate_semantic(valid_output)
        assert is_valid
        
        # Invalid: score out of range (caught by Pydantic)
        # Invalid: no reasons
        invalid_output = ScopeSummaryOutput(
            project_type="commercial",
            scope_summary="Test project summary",
            estimated_size_sqft=12500,
            buyer_fit=BuyerFit(score=50.0, reasons=[])
        )
        
        is_valid, reason = stage.validate_semantic(invalid_output)
        assert not is_valid
        assert "reason" in reason.lower()


class TestPipelineOrchestration:
    """Test pipeline orchestration and idempotency."""
    
    @pytest.mark.asyncio
    async def test_stage_execution_success(self, db, test_report_version):
        """Test successful stage execution creates attempt, output, and events."""
        stage = ScopeSummaryStage()
        
        input_data = {
            "permit_id": str(uuid.uuid4()),
            "city": "TestCity",
            "address_raw": "123 Test St",
            "work_type": "commercial_new_construction",
            "description_raw": "New construction of office building",
            "valuation": 2500000,
            "filed_date": "2024-01-15T00:00:00Z",
            "issued_date": "2024-02-01T00:00:00Z"
        }
        
        result = await run_stage(
            db=db,
            stage_runner=stage,
            report_version_id=test_report_version,
            input_data=input_data,
            idempotency_key="test-key-1"
        )
        
        # Verify attempt created
        assert result["attempt"] is not None
        assert result["attempt"]["status"] == "succeeded"
        assert result["attempt"]["stage_name"] == "scope_summary"
        assert result["is_rerun"] is False
        
        # Verify output created
        assert result["output"] is not None
        assert "project_type" in result["output"]["output"]
        assert "scope_summary" in result["output"]["output"]
        assert "buyer_fit" in result["output"]["output"]
        
        # Verify events created
        events = await db.stage_events.find({"stage_attempt_id": result["attempt"]["_id"]}).to_list(10)
        assert len(events) >= 2  # queued->running, running->succeeded
        
        # Check event transitions
        event_transitions = [(e["event_payload"]["from_status"], e["event_payload"]["to_status"]) for e in events]
        assert ("queued", "running") in event_transitions
        assert ("running", "succeeded") in event_transitions
    
    @pytest.mark.asyncio
    async def test_idempotent_rerun(self, db, test_report_version):
        """Test idempotent rerun returns same attempt/output without re-execution."""
        stage = ScopeSummaryStage()
        
        input_data = {
            "permit_id": str(uuid.uuid4()),
            "city": "TestCity",
            "address_raw": "123 Test St",
            "work_type": "commercial_new_construction",
            "description_raw": "New construction",
            "valuation": 2500000,
            "filed_date": "2024-01-15T00:00:00Z",
            "issued_date": None
        }
        
        # First run
        result1 = await run_stage(
            db=db,
            stage_runner=stage,
            report_version_id=test_report_version,
            input_data=input_data,
            idempotency_key="test-key-idempotent"
        )
        
        attempt_id_1 = result1["attempt"]["_id"]
        output_id_1 = result1["output"]["_id"]
        
        # Second run with same idempotency_key
        result2 = await run_stage(
            db=db,
            stage_runner=stage,
            report_version_id=test_report_version,
            input_data=input_data,
            idempotency_key="test-key-idempotent"
        )
        
        # Verify it's the same attempt/output
        assert result2["is_rerun"] is True
        assert result2["attempt"]["_id"] == attempt_id_1
        assert result2["output"]["_id"] == output_id_1
        
        # Verify no duplicate attempts created
        all_attempts = await db.stage_attempts.find({"report_version_id": test_report_version}).to_list(10)
        assert len(all_attempts) == 1
    
    @pytest.mark.asyncio
    async def test_input_validation_failure(self, db, test_report_version):
        """Test that invalid input fails validation."""
        stage = ScopeSummaryStage()
        
        # Missing required fields
        invalid_input = {
            "permit_id": str(uuid.uuid4()),
            "city": "TestCity"
            # Missing: address_raw, work_type, description_raw, valuation, filed_date
        }
        
        result = await run_stage(
            db=db,
            stage_runner=stage,
            report_version_id=test_report_version,
            input_data=invalid_input,
            idempotency_key="test-invalid-input"
        )
        
        # Should fail
        assert result["attempt"]["status"] == "failed"
        assert result["output"] is None
        assert "error" in result
        assert "validation" in result["error"]["message"].lower()
    
    @pytest.mark.asyncio
    async def test_semantic_validation_failure(self, db, test_report_version):
        """Test that semantic validation is enforced."""
        # Create a custom stage that produces invalid output
        class BadStage(ScopeSummaryStage):
            def execute(self, input_data):
                # Return output that will fail semantic validation
                return {
                    "project_type": "commercial",
                    "scope_summary": "test",  # Too short, will fail semantic validation
                    "estimated_size_sqft": 0,  # Invalid: must be > 0
                    "buyer_fit": {
                        "score": 50.0,
                        "reasons": []  # Invalid: must have at least one reason
                    }
                }
        
        stage = BadStage()
        
        input_data = {
            "permit_id": str(uuid.uuid4()),
            "city": "TestCity",
            "address_raw": "123 Test St",
            "work_type": "commercial",
            "description_raw": "Test",
            "valuation": 100000,
            "filed_date": "2024-01-15T00:00:00Z",
            "issued_date": None
        }
        
        result = await run_stage(
            db=db,
            stage_runner=stage,
            report_version_id=test_report_version,
            input_data=input_data,
            idempotency_key="test-semantic-fail"
        )
        
        # Should fail
        assert result["attempt"]["status"] == "failed"
        assert result["output"] is None
        assert "error" in result
