"""Pipeline orchestrator - manages stage execution."""

from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid
import hashlib
import json
import logging

from app.pipeline.stage_runner import StageRunner
from app.state_machine import (
    can_transition_stage_attempt,
    emit_status_change_event
)

logger = logging.getLogger(__name__)


def compute_idempotency_key(
    report_version_id: str,
    stage_name: str,
    input_hash: str,
    custom_key: Optional[str] = None
) -> str:
    """Compute idempotency key for a stage execution.
    
    If custom_key is provided, use it directly.
    Otherwise, compute from report_version_id + stage_name + input_hash.
    """
    if custom_key:
        return custom_key
    
    # Compute deterministic key
    key_parts = f"{report_version_id}:{stage_name}:{input_hash}"
    return hashlib.sha256(key_parts.encode()).hexdigest()


def compute_input_hash(input_data: Dict[str, Any]) -> str:
    """Compute stable hash of input data."""
    # Sort keys for consistent hashing
    sorted_json = json.dumps(input_data, sort_keys=True)
    return hashlib.sha256(sorted_json.encode()).hexdigest()


async def run_stage(
    db: AsyncIOMotorDatabase,
    stage_runner: StageRunner,
    report_version_id: str,
    input_data: Dict[str, Any],
    idempotency_key: Optional[str] = None,
    provider: str = "deterministic",
    model_id: str = "rule-based"
) -> Dict[str, Any]:
    """Run a pipeline stage with idempotency and state management.
    
    Args:
        db: MongoDB database
        stage_runner: Stage implementation
        report_version_id: Report version ID
        input_data: Stage input data
        idempotency_key: Optional custom idempotency key
        provider: Provider name (for logging)
        model_id: Model ID (for logging)
    
    Returns:
        Dict with attempt and output data
    
    Raises:
        ValueError: If validation fails or report version not found
    """
    stage_name = stage_runner.stage_name
    
    # Verify report version exists
    version = await db.report_versions.find_one({"_id": report_version_id})
    if not version:
        raise ValueError(f"Report version {report_version_id} not found")
    
    # Compute input hash and idempotency key
    input_hash = compute_input_hash(input_data)
    idem_key = compute_idempotency_key(report_version_id, stage_name, input_hash, idempotency_key)
    
    # Check for existing attempt (idempotency)
    existing_attempt = await db.stage_attempts.find_one({
        "report_version_id": report_version_id,
        "stage_name": stage_name,
        "idempotency_key": idem_key
    })
    
    if existing_attempt:
        logger.info(f"Idempotent rerun: returning existing attempt {existing_attempt['_id']}")
        
        # Get existing output
        existing_output = await db.stage_outputs.find_one({
            "stage_attempt_id": existing_attempt["_id"]
        })
        
        return {
            "attempt": existing_attempt,
            "output": existing_output,
            "is_rerun": True
        }
    
    # Create new attempt
    now = datetime.now(timezone.utc).isoformat()
    attempt_id = str(uuid.uuid4())
    
    attempt_doc = {
        "_id": attempt_id,
        "report_version_id": report_version_id,
        "stage_name": stage_name,
        "status": "queued",
        "idempotency_key": idem_key,
        "provider": provider,
        "model_id": model_id,
        "attempt_no": 1,
        "input_hash": input_hash,
        "started_at": None,
        "finished_at": None,
        "error_class": None,
        "error_message": None,
        "metrics": {},
        "created_at": now,
        "updated_at": now
    }
    
    await db.stage_attempts.insert_one(attempt_doc)
    logger.info(f"Created stage attempt {attempt_id} for {stage_name}")
    
    # Transition to running
    start_time = datetime.now(timezone.utc)
    await db.stage_attempts.update_one(
        {"_id": attempt_id},
        {
            "$set": {
                "status": "running",
                "started_at": start_time.isoformat(),
                "updated_at": start_time.isoformat()
            }
        }
    )
    
    # Emit queued -> running event
    await emit_status_change_event(
        db=db,
        collection_name="stage_events",
        entity_id_field="stage_attempt_id",
        entity_id=attempt_id,
        from_status="queued",
        to_status="running",
        reason="Stage execution started"
    )
    
    try:
        # Execute stage
        output_data = stage_runner.run(input_data)
        
        # Calculate metrics
        end_time = datetime.now(timezone.utc)
        latency_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Compute output hash
        output_hash = compute_input_hash(output_data)
        
        # Store output
        output_id = str(uuid.uuid4())
        output_doc = {
            "_id": output_id,
            "stage_attempt_id": attempt_id,
            "output": output_data,
            "output_hash": output_hash,
            "created_at": end_time.isoformat()
        }
        
        await db.stage_outputs.insert_one(output_doc)
        
        # Update attempt to succeeded
        await db.stage_attempts.update_one(
            {"_id": attempt_id},
            {
                "$set": {
                    "status": "succeeded",
                    "finished_at": end_time.isoformat(),
                    "metrics": {
                        "latency_ms": latency_ms,
                        "output_size_bytes": len(json.dumps(output_data))
                    },
                    "updated_at": end_time.isoformat()
                }
            }
        )
        
        # Emit running -> succeeded event
        await emit_status_change_event(
            db=db,
            collection_name="stage_events",
            entity_id_field="stage_attempt_id",
            entity_id=attempt_id,
            from_status="running",
            to_status="succeeded",
            reason="Stage execution completed successfully"
        )
        
        logger.info(f"Stage {stage_name} succeeded: {attempt_id} ({latency_ms}ms)")
        
        # Retrieve final attempt
        final_attempt = await db.stage_attempts.find_one({"_id": attempt_id})
        final_output = await db.stage_outputs.find_one({"stage_attempt_id": attempt_id})
        
        return {
            "attempt": final_attempt,
            "output": final_output,
            "is_rerun": False
        }
        
    except Exception as e:
        # Handle failure
        end_time = datetime.now(timezone.utc)
        latency_ms = int((end_time - start_time).total_seconds() * 1000)
        
        error_class = type(e).__name__
        error_message = str(e)
        
        await db.stage_attempts.update_one(
            {"_id": attempt_id},
            {
                "$set": {
                    "status": "failed",
                    "finished_at": end_time.isoformat(),
                    "error_class": error_class,
                    "error_message": error_message,
                    "metrics": {
                        "latency_ms": latency_ms
                    },
                    "updated_at": end_time.isoformat()
                }
            }
        )
        
        # Emit running -> failed event
        await emit_status_change_event(
            db=db,
            collection_name="stage_events",
            entity_id_field="stage_attempt_id",
            entity_id=attempt_id,
            from_status="running",
            to_status="failed",
            reason=f"{error_class}: {error_message}"
        )
        
        logger.error(f"Stage {stage_name} failed: {attempt_id} - {error_message}")
        
        # Return failed attempt (no output)
        final_attempt = await db.stage_attempts.find_one({"_id": attempt_id})
        
        return {
            "attempt": final_attempt,
            "output": None,
            "is_rerun": False,
            "error": {
                "class": error_class,
                "message": error_message
            }
        }
