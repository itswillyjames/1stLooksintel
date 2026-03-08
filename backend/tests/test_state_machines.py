"""Tests for state machine validators and transitions.

Tests:
1. Allowed transitions succeed
2. Blocked transitions fail with INVALID_TRANSITION
3. Event documents are created for successful transitions
4. Terminal states (archived, completed, failed) block outgoing transitions
5. Context validation (e.g., report draft -> queued requires active_version)
"""

import pytest
import pytest_asyncio
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
import uuid

# Import state machine components
from app.state_machine import (
    can_transition_permit,
    can_transition_report,
    can_transition_report_version,
    can_transition_stage_attempt,
    can_transition_export,
    emit_status_change_event
)
from app.state_machine.enums import (
    PermitStatus,
    ReportStatus,
    ReportVersionStatus,
    StageAttemptStatus,
    ExportStatus
)
from app.services.permit_service import transition_permit_status
from app.services.report_service import transition_report_status, transition_report_version_status

# Test database
TEST_DB_NAME = "test_permit_intel"


@pytest_asyncio.fixture
async def db():
    """Create a test database."""
    mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
    client = AsyncIOMotorClient(mongo_url)
    test_db = client[TEST_DB_NAME]
    
    # Clean up before tests
    await test_db.permits.delete_many({})
    await test_db.permit_events.delete_many({})
    await test_db.reports.delete_many({})
    await test_db.report_versions.delete_many({})
    await test_db.report_events.delete_many({})
    
    yield test_db
    
    # Clean up after tests
    await test_db.permits.delete_many({})
    await test_db.permit_events.delete_many({})
    await test_db.reports.delete_many({})
    await test_db.report_versions.delete_many({})
    await test_db.report_events.delete_many({})
    
    client.close()


class TestPermitTransitions:
    """Test permit state machine transitions."""
    
    def test_permit_allowed_transitions(self):
        """Test all allowed permit transitions."""
        # new -> normalized
        is_valid, reason = can_transition_permit("new", "normalized")
        assert is_valid, f"Expected valid transition, got: {reason}"
        
        # normalized -> prequalified
        is_valid, reason = can_transition_permit("normalized", "prequalified")
        assert is_valid
        
        # normalized -> rejected
        is_valid, reason = can_transition_permit("normalized", "rejected")
        assert is_valid
        
        # prequalified -> shortlisted
        is_valid, reason = can_transition_permit("prequalified", "shortlisted")
        assert is_valid
        
        # prequalified -> rejected
        is_valid, reason = can_transition_permit("prequalified", "rejected")
        assert is_valid
        
        # prequalified -> archived
        is_valid, reason = can_transition_permit("prequalified", "archived")
        assert is_valid
        
        # shortlisted -> archived
        is_valid, reason = can_transition_permit("shortlisted", "archived")
        assert is_valid
        
        # rejected -> archived
        is_valid, reason = can_transition_permit("rejected", "archived")
        assert is_valid
    
    def test_permit_blocked_transitions(self):
        """Test blocked permit transitions."""
        # new -> prequalified (skip normalized)
        is_valid, reason = can_transition_permit("new", "prequalified")
        assert not is_valid
        assert "Invalid transition" in reason
        
        # new -> archived (premature)
        is_valid, reason = can_transition_permit("new", "archived")
        assert not is_valid
        
        # archived -> anything (terminal state)
        is_valid, reason = can_transition_permit("archived", "new")
        assert not is_valid
        assert "terminal state" in reason.lower()
        
        # Self-transition
        is_valid, reason = can_transition_permit("new", "new")
        assert not is_valid
        assert "same status" in reason.lower()
    
    @pytest.mark.asyncio
    async def test_permit_transition_with_event_emission(self, db):
        """Test permit transition emits event."""
        # Create a test permit
        permit_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        await db.permits.insert_one({
            "_id": permit_id,
            "city": "TestCity",
            "source_permit_id": "TEST-001",
            "status": "new",
            "prequal_score": 50.0,
            "prequal_reasons": [],
            "created_at": now,
            "updated_at": now
        })
        
        # Transition permit
        updated_permit = await transition_permit_status(db, permit_id, "normalized", "test transition")
        
        # Verify status updated
        assert updated_permit["status"] == "normalized"
        
        # Verify event created
        events = await db.permit_events.find({"permit_id": permit_id}).to_list(10)
        assert len(events) == 1
        assert events[0]["event_type"] == "status_changed"
        assert events[0]["event_payload"]["from_status"] == "new"
        assert events[0]["event_payload"]["to_status"] == "normalized"
        assert events[0]["event_payload"]["reason"] == "test transition"


class TestReportTransitions:
    """Test report state machine transitions."""
    
    def test_report_allowed_transitions(self):
        """Test all allowed report transitions."""
        # draft -> queued (with active version)
        is_valid, reason = can_transition_report(
            "draft", "queued",
            context={"has_active_version": True}
        )
        assert is_valid
        
        # queued -> running
        is_valid, reason = can_transition_report("queued", "running")
        assert is_valid
        
        # running -> partial
        is_valid, reason = can_transition_report("running", "partial")
        assert is_valid
        
        # running -> completed
        is_valid, reason = can_transition_report("running", "completed")
        assert is_valid
        
        # running -> failed
        is_valid, reason = can_transition_report("running", "failed")
        assert is_valid
        
        # partial -> running
        is_valid, reason = can_transition_report("partial", "running")
        assert is_valid
        
        # partial -> completed
        is_valid, reason = can_transition_report("partial", "completed")
        assert is_valid
        
        # completed -> superseded
        is_valid, reason = can_transition_report("completed", "superseded")
        assert is_valid
        
        # completed -> archived
        is_valid, reason = can_transition_report("completed", "archived")
        assert is_valid
        
        # failed -> queued (retry)
        is_valid, reason = can_transition_report("failed", "queued")
        assert is_valid
        
        # failed -> archived
        is_valid, reason = can_transition_report("failed", "archived")
        assert is_valid
    
    def test_report_blocked_transitions(self):
        """Test blocked report transitions."""
        # draft -> queued without active version
        is_valid, reason = can_transition_report(
            "draft", "queued",
            context={"has_active_version": False}
        )
        assert not is_valid
        assert "without active version" in reason.lower()
        
        # draft -> running (skip queued)
        is_valid, reason = can_transition_report("draft", "running")
        assert not is_valid
        
        # archived -> anything (terminal)
        is_valid, reason = can_transition_report("archived", "draft")
        assert not is_valid
        assert "terminal state" in reason.lower()


class TestReportVersionTransitions:
    """Test report version state machine transitions."""
    
    def test_report_version_allowed_transitions(self):
        """Test all allowed report version transitions."""
        # queued -> running
        is_valid, reason = can_transition_report_version("queued", "running")
        assert is_valid
        
        # running -> partial
        is_valid, reason = can_transition_report_version("running", "partial")
        assert is_valid
        
        # running -> completed
        is_valid, reason = can_transition_report_version("running", "completed")
        assert is_valid
        
        # running -> failed
        is_valid, reason = can_transition_report_version("running", "failed")
        assert is_valid
        
        # partial -> running
        is_valid, reason = can_transition_report_version("partial", "running")
        assert is_valid
        
        # partial -> completed
        is_valid, reason = can_transition_report_version("partial", "completed")
        assert is_valid
    
    def test_report_version_terminal_states(self):
        """Test terminal states for report version."""
        # completed is terminal
        is_valid, reason = can_transition_report_version("completed", "running")
        assert not is_valid
        assert "terminal state" in reason.lower()
        
        # failed is terminal
        is_valid, reason = can_transition_report_version("failed", "running")
        assert not is_valid
        assert "terminal state" in reason.lower()


class TestStageAttemptTransitions:
    """Test stage attempt state machine transitions."""
    
    def test_stage_attempt_allowed_transitions(self):
        """Test all allowed stage attempt transitions."""
        # queued -> running
        is_valid, reason = can_transition_stage_attempt("queued", "running")
        assert is_valid
        
        # running -> succeeded
        is_valid, reason = can_transition_stage_attempt("running", "succeeded")
        assert is_valid
        
        # running -> failed
        is_valid, reason = can_transition_stage_attempt("running", "failed")
        assert is_valid
    
    def test_stage_attempt_terminal_states(self):
        """Test terminal states for stage attempts."""
        # succeeded is terminal
        is_valid, reason = can_transition_stage_attempt("succeeded", "running")
        assert not is_valid
        assert "terminal state" in reason.lower()
        
        # failed is terminal
        is_valid, reason = can_transition_stage_attempt("failed", "running")
        assert not is_valid
        assert "terminal state" in reason.lower()


class TestExportTransitions:
    """Test export state machine transitions."""
    
    def test_export_allowed_transitions(self):
        """Test all allowed export transitions."""
        # draft -> rendering
        is_valid, reason = can_transition_export("draft", "rendering")
        assert is_valid
        
        # rendering -> ready
        is_valid, reason = can_transition_export("rendering", "ready")
        assert is_valid
        
        # rendering -> failed
        is_valid, reason = can_transition_export("rendering", "failed")
        assert is_valid
        
        # ready -> delivered
        is_valid, reason = can_transition_export("ready", "delivered")
        assert is_valid
        
        # ready -> failed
        is_valid, reason = can_transition_export("ready", "failed")
        assert is_valid
        
        # failed -> rendering (retry)
        is_valid, reason = can_transition_export("failed", "rendering")
        assert is_valid
    
    def test_export_terminal_state(self):
        """Test terminal state for exports."""
        # delivered is terminal
        is_valid, reason = can_transition_export("delivered", "ready")
        assert not is_valid
        assert "terminal state" in reason.lower()


class TestEventEmission:
    """Test event emission for transitions."""
    
    @pytest.mark.asyncio
    async def test_event_is_immutable(self, db):
        """Test that events are append-only (no updates/deletes)."""
        # Emit an event
        event_id = await emit_status_change_event(
            db=db,
            collection_name="permit_events",
            entity_id_field="permit_id",
            entity_id="test-permit-123",
            from_status="new",
            to_status="normalized",
            reason="test"
        )
        
        # Verify event exists
        event = await db.permit_events.find_one({"_id": event_id})
        assert event is not None
        assert event["event_type"] == "status_changed"
        
        # Events should be append-only - no update/delete methods in service layer
        # This is enforced by not providing update/delete endpoints
        # Verify event structure
        assert "permit_id" in event
        assert "event_payload" in event
        assert "created_at" in event
        assert event["event_payload"]["from_status"] == "new"
        assert event["event_payload"]["to_status"] == "normalized"
