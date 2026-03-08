"""Tests for Milestone 5: Export HTML Dossier + Manifest."""

import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.services.export_service import (
    render_dossier_export,
    get_export,
    list_exports,
    render_dossier_html_v1,
    build_manifest,
    gather_export_data
)
from datetime import datetime, timezone
import uuid
import os


@pytest_asyncio.fixture
async def test_db():
    """Create a test database connection."""
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    client = AsyncIOMotorClient(mongo_url)
    db_name = f"test_export_{uuid.uuid4().hex[:8]}"
    db = client[db_name]
    
    yield db
    
    # Cleanup
    await client.drop_database(db_name)
    client.close()


@pytest_asyncio.fixture
async def seeded_report_version(test_db):
    """Create a seeded report version with all required data."""
    now = datetime.now(timezone.utc).isoformat()
    
    # Create permit
    permit_id = str(uuid.uuid4())
    permit = {
        "_id": permit_id,
        "city": "San Francisco",
        "source_permit_id": "SF-2024-001",
        "address_raw": "123 Main St, San Francisco, CA",
        "work_type": "commercial_remodel",
        "description_raw": "Interior renovation of office space",
        "valuation": 500000,
        "filed_date": "2024-01-15",
        "owner_raw": "Acme Properties LLC",
        "contractor_raw": "BuildRight Construction",
        "applicant_raw": "John Smith",
        "status": "prequalified",
        "created_at": now,
        "updated_at": now
    }
    await test_db.permits.insert_one(permit)
    
    # Create report
    report_id = str(uuid.uuid4())
    report = {
        "_id": report_id,
        "permit_id": permit_id,
        "status": "running",
        "active_version_id": None,
        "created_at": now,
        "updated_at": now
    }
    await test_db.reports.insert_one(report)
    
    # Create report version with snapshot
    version_id = str(uuid.uuid4())
    report_version = {
        "_id": version_id,
        "report_id": report_id,
        "version": 1,
        "snapshot": {
            "permit": permit,
            "run_config": {"stages": ["scope_summary"]}
        },
        "status": "completed",
        "created_at": now,
        "updated_at": now
    }
    await test_db.report_versions.insert_one(report_version)
    await test_db.reports.update_one(
        {"_id": report_id},
        {"$set": {"active_version_id": version_id}}
    )
    
    # Create stage attempt (scope_summary)
    attempt_id = str(uuid.uuid4())
    stage_attempt = {
        "_id": attempt_id,
        "report_version_id": version_id,
        "stage_name": "scope_summary",
        "status": "succeeded",
        "provider": "deterministic",
        "model_id": "rule_based_v1",
        "attempt_no": 1,
        "idempotency_key": str(uuid.uuid4()),
        "started_at": now,
        "finished_at": now,
        "created_at": now,
        "updated_at": now
    }
    await test_db.stage_attempts.insert_one(stage_attempt)
    
    # Create stage output
    output_id = str(uuid.uuid4())
    stage_output = {
        "_id": output_id,
        "stage_attempt_id": attempt_id,
        "output_data": {
            "project_type": "commercial_remodel",
            "scope_summary": "Interior renovation of existing office space including new flooring, lighting, and HVAC upgrades.",
            "estimated_size": "medium",
            "buyer_fit_score": 0.85,
            "buyer_fit_rationale": "High-value commercial project with clear scope"
        },
        "created_at": now
    }
    await test_db.stage_outputs.insert_one(stage_output)
    
    # Create entity and suggestion
    entity_id = str(uuid.uuid4())
    entity = {
        "_id": entity_id,
        "canonical_name": "BuildRight Construction",
        "entity_type": "organization",
        "status": "active",
        "created_at": now,
        "updated_at": now
    }
    await test_db.entities.insert_one(entity)
    
    suggestion_id = str(uuid.uuid4())
    suggestion = {
        "_id": suggestion_id,
        "report_version_id": version_id,
        "observed_name": "BuildRight Construction",
        "observed_role": "contractor",
        "observed_source": "permit.contractor_raw",
        "alias_norm": "buildright construction",
        "candidate_entity_ids": [entity_id],
        "match_type": "exact",
        "confidence": 1.0,
        "status": "open",
        "created_at": now,
        "updated_at": now
    }
    await test_db.entity_match_suggestions.insert_one(suggestion)
    
    return {
        "permit_id": permit_id,
        "report_id": report_id,
        "version_id": version_id,
        "attempt_id": attempt_id,
        "output_id": output_id,
        "entity_id": entity_id,
        "suggestion_id": suggestion_id,
        "permit": permit
    }


class TestDeterministicHtmlSnapshot:
    """Test that HTML output is deterministic given same inputs."""
    
    @pytest.mark.asyncio
    async def test_html_output_is_stable(self, test_db, seeded_report_version):
        """Same inputs produce identical HTML output."""
        version_id = seeded_report_version["version_id"]
        
        # Gather data
        data = await gather_export_data(test_db, version_id)
        
        export_id = "test-export-id"
        template_version = "v1"
        
        # Render twice
        html1 = render_dossier_html_v1(
            permit=data["permit"],
            scope_summary=data["scope_summary_output"],
            entities=data["entities"],
            entity_suggestions=data["entity_suggestions"],
            export_id=export_id,
            template_version=template_version
        )
        
        html2 = render_dossier_html_v1(
            permit=data["permit"],
            scope_summary=data["scope_summary_output"],
            entities=data["entities"],
            entity_suggestions=data["entity_suggestions"],
            export_id=export_id,
            template_version=template_version
        )
        
        assert html1 == html2, "HTML output should be deterministic"
    
    @pytest.mark.asyncio
    async def test_html_contains_permit_info(self, test_db, seeded_report_version):
        """HTML includes permit information."""
        version_id = seeded_report_version["version_id"]
        data = await gather_export_data(test_db, version_id)
        
        html = render_dossier_html_v1(
            permit=data["permit"],
            scope_summary=data["scope_summary_output"],
            entities=data["entities"],
            entity_suggestions=data["entity_suggestions"],
            export_id="test",
            template_version="v1"
        )
        
        assert "123 Main St" in html
        assert "San Francisco" in html
        assert "BuildRight Construction" in html
        assert "$500,000" in html or "500000" in html
    
    @pytest.mark.asyncio
    async def test_html_contains_scope_summary(self, test_db, seeded_report_version):
        """HTML includes scope summary when present."""
        version_id = seeded_report_version["version_id"]
        data = await gather_export_data(test_db, version_id)
        
        html = render_dossier_html_v1(
            permit=data["permit"],
            scope_summary=data["scope_summary_output"],
            entities=data["entities"],
            entity_suggestions=data["entity_suggestions"],
            export_id="test",
            template_version="v1"
        )
        
        assert "commercial_remodel" in html
        assert "Interior renovation" in html
        assert "0.85" in html


class TestIdempotency:
    """Test that duplicate exports return the same export_id."""
    
    @pytest.mark.asyncio
    async def test_idempotent_rerun_returns_same_export_id(self, test_db, seeded_report_version):
        """Running export twice returns the same export."""
        version_id = seeded_report_version["version_id"]
        
        # First render
        result1 = await render_dossier_export(
            db=test_db,
            report_version_id=version_id,
            template_version="v1"
        )
        
        assert result1["is_rerun"] is False
        export_id_1 = result1["export"]["_id"]
        
        # Second render (should be idempotent)
        result2 = await render_dossier_export(
            db=test_db,
            report_version_id=version_id,
            template_version="v1"
        )
        
        assert result2["is_rerun"] is True
        export_id_2 = result2["export"]["_id"]
        
        assert export_id_1 == export_id_2, "Idempotent reruns should return same export_id"
    
    @pytest.mark.asyncio
    async def test_different_template_creates_new_export(self, test_db, seeded_report_version):
        """Different template_version creates a new export."""
        version_id = seeded_report_version["version_id"]
        
        # First render with v1
        result1 = await render_dossier_export(
            db=test_db,
            report_version_id=version_id,
            template_version="v1"
        )
        
        # Try with unknown version (should fail)
        with pytest.raises(ValueError, match="Unknown template version"):
            await render_dossier_export(
                db=test_db,
                report_version_id=version_id,
                template_version="v2"
            )


class TestManifest:
    """Test that manifest includes required fields and references."""
    
    @pytest.mark.asyncio
    async def test_manifest_includes_required_fields(self, test_db, seeded_report_version):
        """Manifest contains all required fields."""
        version_id = seeded_report_version["version_id"]
        
        result = await render_dossier_export(
            db=test_db,
            report_version_id=version_id,
            template_version="v1"
        )
        
        manifest = result["export"]["manifest"]
        
        # Required top-level fields
        assert "export_id" in manifest
        assert "report_version_id" in manifest
        assert "export_type" in manifest
        assert "template_version" in manifest
        assert "rendered_at" in manifest
        
        # Required reference arrays
        assert "stage_attempts" in manifest
        assert "entities" in manifest
        assert "entity_suggestions" in manifest
        assert "evidence_links" in manifest
        
        # Snapshot references
        assert "permit_snapshot" in manifest
        assert "run_config_snapshot" in manifest
    
    @pytest.mark.asyncio
    async def test_manifest_references_stage_attempts(self, test_db, seeded_report_version):
        """Manifest includes stage attempt references."""
        version_id = seeded_report_version["version_id"]
        attempt_id = seeded_report_version["attempt_id"]
        
        result = await render_dossier_export(
            db=test_db,
            report_version_id=version_id,
            template_version="v1"
        )
        
        manifest = result["export"]["manifest"]
        stage_attempts = manifest["stage_attempts"]
        
        assert len(stage_attempts) >= 1
        
        # Find scope_summary attempt
        scope_attempt = next((a for a in stage_attempts if a["stage_name"] == "scope_summary"), None)
        assert scope_attempt is not None
        assert scope_attempt["attempt_id"] == attempt_id
        assert scope_attempt["status"] == "succeeded"
    
    @pytest.mark.asyncio
    async def test_manifest_references_entities(self, test_db, seeded_report_version):
        """Manifest includes entity references."""
        version_id = seeded_report_version["version_id"]
        entity_id = seeded_report_version["entity_id"]
        
        result = await render_dossier_export(
            db=test_db,
            report_version_id=version_id,
            template_version="v1"
        )
        
        manifest = result["export"]["manifest"]
        entities = manifest["entities"]
        
        assert len(entities) >= 1
        
        entity_ref = next((e for e in entities if e["entity_id"] == entity_id), None)
        assert entity_ref is not None
        assert entity_ref["canonical_name"] == "BuildRight Construction"
    
    @pytest.mark.asyncio
    async def test_manifest_references_suggestions(self, test_db, seeded_report_version):
        """Manifest includes entity suggestion references."""
        version_id = seeded_report_version["version_id"]
        suggestion_id = seeded_report_version["suggestion_id"]
        
        result = await render_dossier_export(
            db=test_db,
            report_version_id=version_id,
            template_version="v1"
        )
        
        manifest = result["export"]["manifest"]
        suggestions = manifest["entity_suggestions"]
        
        assert len(suggestions) >= 1
        
        suggestion_ref = next((s for s in suggestions if s["suggestion_id"] == suggestion_id), None)
        assert suggestion_ref is not None
        assert suggestion_ref["observed_name"] == "BuildRight Construction"
        assert suggestion_ref["match_type"] == "exact"


class TestExportStatus:
    """Test export status transitions."""
    
    @pytest.mark.asyncio
    async def test_successful_export_status_is_ready(self, test_db, seeded_report_version):
        """Successful export ends in 'ready' status."""
        version_id = seeded_report_version["version_id"]
        
        result = await render_dossier_export(
            db=test_db,
            report_version_id=version_id,
            template_version="v1"
        )
        
        assert result["export"]["status"] == "ready"
    
    @pytest.mark.asyncio
    async def test_export_event_created(self, test_db, seeded_report_version):
        """Export event is created on render."""
        version_id = seeded_report_version["version_id"]
        
        result = await render_dossier_export(
            db=test_db,
            report_version_id=version_id,
            template_version="v1"
        )
        
        export_id = result["export"]["_id"]
        
        # Check event was created
        event = await test_db.export_events.find_one({"export_id": export_id})
        assert event is not None
        assert event["event_type"] == "rendered"
        assert event["to_status"] == "ready"
