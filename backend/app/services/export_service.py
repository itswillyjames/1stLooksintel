"""Export service for HTML dossier rendering and manifest generation.

DETERMINISM:
- HTML output is stable given same inputs (no random IDs, timestamps in content)
- Manifest references are sorted for consistent ordering
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
import logging
import html

logger = logging.getLogger(__name__)

# Template version registry
TEMPLATE_VERSIONS = {"v1"}


def escape_html(text: str) -> str:
    """Safely escape HTML content."""
    if text is None:
        return ""
    return html.escape(str(text))


def render_dossier_html_v1(
    permit: Dict[str, Any],
    scope_summary: Optional[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    entity_suggestions: List[Dict[str, Any]],
    export_id: str,
    template_version: str
) -> str:
    """Render HTML dossier using v1 template.
    
    DETERMINISTIC: Output is stable given same inputs.
    - No timestamps in rendered content
    - Entities/suggestions sorted by name for consistent ordering
    """
    # Sort entities and suggestions for deterministic output
    sorted_entities = sorted(entities, key=lambda e: e.get("canonical_name", ""))
    sorted_suggestions = sorted(entity_suggestions, key=lambda s: s.get("observed_name", ""))
    
    # Build entities section
    entities_html = ""
    if sorted_entities:
        entities_rows = ""
        for e in sorted_entities:
            entities_rows += f"""
            <tr>
                <td>{escape_html(e.get('canonical_name', 'N/A'))}</td>
                <td>{escape_html(e.get('entity_type', 'N/A'))}</td>
                <td>{escape_html(e.get('status', 'N/A'))}</td>
            </tr>"""
        entities_html = f"""
        <section class="entities">
            <h2>Extracted Entities</h2>
            <table>
                <thead>
                    <tr><th>Name</th><th>Type</th><th>Status</th></tr>
                </thead>
                <tbody>{entities_rows}</tbody>
            </table>
        </section>"""
    
    # Build suggestions section
    suggestions_html = ""
    if sorted_suggestions:
        suggestions_rows = ""
        for s in sorted_suggestions:
            suggestions_rows += f"""
            <tr>
                <td>{escape_html(s.get('observed_name', 'N/A'))}</td>
                <td>{escape_html(s.get('observed_role', 'N/A'))}</td>
                <td>{escape_html(s.get('match_type', 'N/A'))}</td>
                <td>{escape_html(s.get('status', 'N/A'))}</td>
            </tr>"""
        suggestions_html = f"""
        <section class="suggestions">
            <h2>Entity Match Suggestions</h2>
            <table>
                <thead>
                    <tr><th>Observed Name</th><th>Role</th><th>Match Type</th><th>Status</th></tr>
                </thead>
                <tbody>{suggestions_rows}</tbody>
            </table>
        </section>"""
    
    # Build scope summary section
    scope_html = ""
    if scope_summary:
        scope_html = f"""
        <section class="scope-summary">
            <h2>Scope Summary</h2>
            <dl>
                <dt>Project Type</dt>
                <dd>{escape_html(scope_summary.get('project_type', 'N/A'))}</dd>
                <dt>Summary</dt>
                <dd>{escape_html(scope_summary.get('scope_summary', 'N/A'))}</dd>
                <dt>Estimated Size</dt>
                <dd>{escape_html(scope_summary.get('estimated_size', 'N/A'))}</dd>
                <dt>Buyer Fit Score</dt>
                <dd>{escape_html(str(scope_summary.get('buyer_fit_score', 'N/A')))}</dd>
                <dt>Buyer Fit Rationale</dt>
                <dd>{escape_html(scope_summary.get('buyer_fit_rationale', 'N/A'))}</dd>
            </dl>
        </section>"""
    
    # Assemble full HTML
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Permit Dossier - {escape_html(permit.get('address_raw', 'Unknown'))}</title>
    <meta name="generator" content="PermitIntel Dossier Export {template_version}">
    <meta name="export-id" content="{export_id}">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; line-height: 1.6; }}
        h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
        h2 {{ color: #444; margin-top: 2rem; }}
        .permit-info {{ background: #f5f5f5; padding: 1rem; border-radius: 8px; }}
        .permit-info dl {{ display: grid; grid-template-columns: 200px 1fr; gap: 0.5rem; }}
        .permit-info dt {{ font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 1rem 0; }}
        th, td {{ border: 1px solid #ddd; padding: 0.75rem; text-align: left; }}
        th {{ background: #f0f0f0; }}
        section {{ margin-bottom: 2rem; }}
        dl {{ display: grid; grid-template-columns: 200px 1fr; gap: 0.5rem; }}
        dt {{ font-weight: bold; color: #555; }}
    </style>
</head>
<body>
    <header>
        <h1>Permit Intelligence Dossier</h1>
    </header>
    
    <section class="permit-info">
        <h2>Permit Information</h2>
        <dl>
            <dt>Address</dt>
            <dd>{escape_html(permit.get('address_raw', 'N/A'))}</dd>
            <dt>City</dt>
            <dd>{escape_html(permit.get('city', 'N/A'))}</dd>
            <dt>Permit ID</dt>
            <dd>{escape_html(permit.get('source_permit_id', 'N/A'))}</dd>
            <dt>Work Type</dt>
            <dd>{escape_html(permit.get('work_type', 'N/A'))}</dd>
            <dt>Description</dt>
            <dd>{escape_html(permit.get('description_raw', 'N/A'))}</dd>
            <dt>Valuation</dt>
            <dd>${permit.get('valuation', 0):,}</dd>
            <dt>Filed Date</dt>
            <dd>{escape_html(permit.get('filed_date', 'N/A'))}</dd>
            <dt>Owner</dt>
            <dd>{escape_html(permit.get('owner_raw', 'N/A'))}</dd>
            <dt>Contractor</dt>
            <dd>{escape_html(permit.get('contractor_raw', 'N/A'))}</dd>
        </dl>
    </section>
    
    {scope_html}
    {entities_html}
    {suggestions_html}
    
    <footer>
        <p><small>Generated by PermitIntel - Template {template_version}</small></p>
    </footer>
</body>
</html>"""
    
    return html_content


async def gather_export_data(
    db: AsyncIOMotorDatabase,
    report_version_id: str
) -> Dict[str, Any]:
    """Gather all data needed for export.
    
    Returns:
        {
            "report_version": {...},
            "permit": {...},
            "stage_attempts": [...],
            "scope_summary_output": {...} or None,
            "entities": [...],
            "entity_suggestions": [...],
            "evidence_links": [...]
        }
    """
    # Get report version with snapshot
    report_version = await db.report_versions.find_one({"_id": report_version_id})
    if not report_version:
        raise ValueError(f"Report version {report_version_id} not found")
    
    snapshot = report_version.get("snapshot", {})
    permit = snapshot.get("permit", {})
    run_config = snapshot.get("run_config", {})
    
    # Get stage attempts for this version
    stage_attempts = await db.stage_attempts.find(
        {"report_version_id": report_version_id}
    ).sort("created_at", 1).to_list(length=100)
    
    # Get scope_summary output (if exists)
    scope_summary_output = None
    for attempt in stage_attempts:
        if attempt.get("stage_name") == "scope_summary" and attempt.get("status") == "succeeded":
            output = await db.stage_outputs.find_one({"stage_attempt_id": attempt["_id"]})
            if output:
                scope_summary_output = output.get("output_data", {})
            break
    
    # Get entities extracted for this report version
    # First get suggestions to find which entities were created
    suggestions = await db.entity_match_suggestions.find(
        {"report_version_id": report_version_id}
    ).to_list(length=1000)
    
    # Get unique entity IDs from suggestions
    entity_ids = set()
    for s in suggestions:
        entity_ids.update(s.get("candidate_entity_ids", []))
    
    # Fetch entities
    entities = []
    if entity_ids:
        entities = await db.entities.find(
            {"_id": {"$in": list(entity_ids)}}
        ).to_list(length=1000)
    
    # Get evidence links for this report version (immutable, read-only)
    evidence_links = await db.evidence_links.find(
        {"link_type": "report_version", "link_id": report_version_id}
    ).to_list(length=1000)
    
    return {
        "report_version": report_version,
        "permit": permit,
        "run_config": run_config,
        "stage_attempts": stage_attempts,
        "scope_summary_output": scope_summary_output,
        "entities": entities,
        "entity_suggestions": suggestions,
        "evidence_links": evidence_links
    }


def build_manifest(
    export_id: str,
    report_version_id: str,
    export_type: str,
    template_version: str,
    rendered_at: str,
    data: Dict[str, Any]
) -> Dict[str, Any]:
    """Build export manifest JSON.
    
    DETERMINISTIC: References are sorted for consistent ordering.
    """
    # Build stage attempts reference (sorted by stage_name for determinism)
    stage_refs = []
    for attempt in sorted(data["stage_attempts"], key=lambda a: a.get("stage_name", "")):
        stage_refs.append({
            "stage_name": attempt.get("stage_name"),
            "attempt_id": attempt.get("_id"),
            "status": attempt.get("status")
        })
    
    # Add output_id for succeeded attempts
    for ref in stage_refs:
        if ref["status"] == "succeeded":
            # Find output
            for attempt in data["stage_attempts"]:
                if attempt["_id"] == ref["attempt_id"]:
                    # Output ID is derived from attempt
                    pass
    
    # Build entity references (sorted by canonical_name)
    entity_refs = []
    for e in sorted(data["entities"], key=lambda x: x.get("canonical_name", "")):
        entity_refs.append({
            "entity_id": e.get("_id"),
            "canonical_name": e.get("canonical_name"),
            "entity_type": e.get("entity_type"),
            "status": e.get("status")
        })
    
    # Build suggestion references (sorted by observed_name)
    suggestion_refs = []
    for s in sorted(data["entity_suggestions"], key=lambda x: x.get("observed_name", "")):
        suggestion_refs.append({
            "suggestion_id": s.get("_id"),
            "observed_name": s.get("observed_name"),
            "observed_role": s.get("observed_role"),
            "match_type": s.get("match_type"),
            "status": s.get("status")
        })
    
    # Build evidence link references (sorted by evidence_id)
    evidence_refs = []
    for el in sorted(data["evidence_links"], key=lambda x: x.get("evidence_id", "")):
        evidence_refs.append({
            "evidence_id": el.get("evidence_id"),
            "link_type": el.get("link_type"),
            "link_id": el.get("link_id")
        })
    
    return {
        "export_id": export_id,
        "report_version_id": report_version_id,
        "export_type": export_type,
        "template_version": template_version,
        "rendered_at": rendered_at,
        "stage_attempts": stage_refs,
        "entities": entity_refs,
        "entity_suggestions": suggestion_refs,
        "evidence_links": evidence_refs,
        "permit_snapshot": data["permit"],
        "run_config_snapshot": data["run_config"]
    }


async def render_dossier_export(
    db: AsyncIOMotorDatabase,
    report_version_id: str,
    template_version: str = "v1",
    idempotency_key: Optional[str] = None
) -> Dict[str, Any]:
    """Render HTML dossier export with manifest.
    
    IDEMPOTENT: Same (report_version_id, export_type, template_version) returns existing export.
    
    Process:
    1. Check for existing export (idempotency)
    2. Create export record in 'draft' status
    3. Gather all data
    4. Render HTML
    5. Build manifest
    6. Update export to 'ready' with content
    7. Create export_event
    
    Returns:
        {
            "export": {...},
            "is_rerun": bool
        }
    """
    if template_version not in TEMPLATE_VERSIONS:
        raise ValueError(f"Unknown template version: {template_version}. Valid: {TEMPLATE_VERSIONS}")
    
    export_type = "html_dossier"
    
    # Check for existing export (idempotency via unique index)
    existing = await db.exports.find_one({
        "report_version_id": report_version_id,
        "export_type": export_type,
        "template_version": template_version
    })
    
    if existing:
        logger.info(f"Returning existing export {existing['_id']} (idempotent)")
        return {
            "export": existing,
            "is_rerun": True
        }
    
    # Verify report version exists
    report_version = await db.report_versions.find_one({"_id": report_version_id})
    if not report_version:
        raise ValueError(f"Report version {report_version_id} not found")
    
    now = datetime.now(timezone.utc).isoformat()
    export_id = str(uuid.uuid4())
    
    # Create export record in draft status
    export_doc = {
        "_id": export_id,
        "report_version_id": report_version_id,
        "export_type": export_type,
        "template_version": template_version,
        "status": "draft",
        "html_content": None,
        "manifest": None,
        "idempotency_key": idempotency_key or export_id,
        "created_at": now,
        "updated_at": now
    }
    
    try:
        await db.exports.insert_one(export_doc)
    except Exception as e:
        # Handle race condition - another request created the export
        if "duplicate key" in str(e).lower():
            existing = await db.exports.find_one({
                "report_version_id": report_version_id,
                "export_type": export_type,
                "template_version": template_version
            })
            if existing:
                return {"export": existing, "is_rerun": True}
        raise
    
    # Transition to rendering
    await db.exports.update_one(
        {"_id": export_id},
        {"$set": {"status": "rendering", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    try:
        # Gather all data
        data = await gather_export_data(db, report_version_id)
        
        # Render HTML
        html_content = render_dossier_html_v1(
            permit=data["permit"],
            scope_summary=data["scope_summary_output"],
            entities=data["entities"],
            entity_suggestions=data["entity_suggestions"],
            export_id=export_id,
            template_version=template_version
        )
        
        # Build manifest
        manifest = build_manifest(
            export_id=export_id,
            report_version_id=report_version_id,
            export_type=export_type,
            template_version=template_version,
            rendered_at=now,
            data=data
        )
        
        # Update export to ready
        final_update = datetime.now(timezone.utc).isoformat()
        await db.exports.update_one(
            {"_id": export_id},
            {"$set": {
                "status": "ready",
                "html_content": html_content,
                "manifest": manifest,
                "updated_at": final_update
            }}
        )
        
        # Create export event
        event_doc = {
            "_id": str(uuid.uuid4()),
            "export_id": export_id,
            "event_type": "rendered",
            "from_status": "rendering",
            "to_status": "ready",
            "created_at": final_update
        }
        await db.export_events.insert_one(event_doc)
        
        # Fetch final export
        final_export = await db.exports.find_one({"_id": export_id})
        
        logger.info(f"Export {export_id} rendered successfully")
        return {
            "export": final_export,
            "is_rerun": False
        }
        
    except Exception as e:
        # Mark as failed
        await db.exports.update_one(
            {"_id": export_id},
            {"$set": {
                "status": "failed",
                "error_message": str(e),
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        logger.error(f"Export {export_id} failed: {e}")
        raise


async def get_export(db: AsyncIOMotorDatabase, export_id: str) -> Optional[Dict[str, Any]]:
    """Get export by ID."""
    return await db.exports.find_one({"_id": export_id})


async def list_exports(
    db: AsyncIOMotorDatabase,
    report_version_id: str,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """List exports for a report version."""
    query = {"report_version_id": report_version_id}
    if status:
        query["status"] = status
    
    exports = await db.exports.find(query).sort("created_at", -1).to_list(length=100)
    return exports
