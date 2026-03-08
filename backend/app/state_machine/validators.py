"""Transition validators for state machines.

Each validator returns (is_valid: bool, reason: str).
"""

from typing import Tuple, Dict, Any, Optional
from app.state_machine.enums import (
    PermitStatus,
    ReportStatus,
    ReportVersionStatus,
    StageAttemptStatus,
    ExportStatus
)


def can_transition_permit(
    from_status: str,
    to_status: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """Validate permit status transition.
    
    Rules:
    - new -> normalized
    - normalized -> prequalified | rejected
    - prequalified -> shortlisted | rejected | archived
    - shortlisted -> archived
    - rejected -> archived
    - archived is terminal (no transitions out)
    """
    # Normalize to enum values
    try:
        from_s = PermitStatus(from_status)
        to_s = PermitStatus(to_status)
    except ValueError as e:
        return False, f"Invalid status value: {e}"
    
    # No self-transitions
    if from_s == to_s:
        return False, "Cannot transition to the same status"
    
    # Terminal state check
    if from_s == PermitStatus.ARCHIVED:
        return False, "Cannot transition from archived (terminal state)"
    
    # Define allowed transitions
    allowed_transitions = {
        PermitStatus.NEW: [PermitStatus.NORMALIZED],
        PermitStatus.NORMALIZED: [PermitStatus.PREQUALIFIED, PermitStatus.REJECTED],
        PermitStatus.PREQUALIFIED: [PermitStatus.SHORTLISTED, PermitStatus.REJECTED, PermitStatus.ARCHIVED],
        PermitStatus.SHORTLISTED: [PermitStatus.ARCHIVED],
        PermitStatus.REJECTED: [PermitStatus.ARCHIVED],
    }
    
    if to_s not in allowed_transitions.get(from_s, []):
        return False, f"Invalid transition: {from_status} -> {to_status}"
    
    return True, "Transition allowed"


def can_transition_report(
    from_status: str,
    to_status: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """Validate report status transition.
    
    Rules:
    - draft -> queued (requires permit_id exists)
    - queued -> running
    - running -> partial | completed | failed
    - partial -> running | completed | failed
    - completed -> superseded | archived
    - failed -> queued | archived
    - superseded -> archived
    - archived is terminal
    """
    try:
        from_s = ReportStatus(from_status)
        to_s = ReportStatus(to_status)
    except ValueError as e:
        return False, f"Invalid status value: {e}"
    
    if from_s == to_s:
        return False, "Cannot transition to the same status"
    
    if from_s == ReportStatus.ARCHIVED:
        return False, "Cannot transition from archived (terminal state)"
    
    # Special context validation for draft -> queued
    if from_s == ReportStatus.DRAFT and to_s == ReportStatus.QUEUED:
        if context and not context.get("has_active_version"):
            return False, "Cannot queue report without active version"
    
    allowed_transitions = {
        ReportStatus.DRAFT: [ReportStatus.QUEUED],
        ReportStatus.QUEUED: [ReportStatus.RUNNING],
        ReportStatus.RUNNING: [ReportStatus.PARTIAL, ReportStatus.COMPLETED, ReportStatus.FAILED],
        ReportStatus.PARTIAL: [ReportStatus.RUNNING, ReportStatus.COMPLETED, ReportStatus.FAILED],
        ReportStatus.COMPLETED: [ReportStatus.SUPERSEDED, ReportStatus.ARCHIVED],
        ReportStatus.FAILED: [ReportStatus.QUEUED, ReportStatus.ARCHIVED],
        ReportStatus.SUPERSEDED: [ReportStatus.ARCHIVED],
    }
    
    if to_s not in allowed_transitions.get(from_s, []):
        return False, f"Invalid transition: {from_status} -> {to_status}"
    
    return True, "Transition allowed"


def can_transition_report_version(
    from_status: str,
    to_status: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """Validate report version status transition.
    
    Rules:
    - queued -> running
    - running -> partial | completed | failed
    - partial -> running | completed | failed
    - completed and failed are terminal
    """
    try:
        from_s = ReportVersionStatus(from_status)
        to_s = ReportVersionStatus(to_status)
    except ValueError as e:
        return False, f"Invalid status value: {e}"
    
    if from_s == to_s:
        return False, "Cannot transition to the same status"
    
    # Terminal states
    if from_s in [ReportVersionStatus.COMPLETED, ReportVersionStatus.FAILED]:
        return False, f"Cannot transition from {from_status} (terminal state)"
    
    allowed_transitions = {
        ReportVersionStatus.QUEUED: [ReportVersionStatus.RUNNING],
        ReportVersionStatus.RUNNING: [ReportVersionStatus.PARTIAL, ReportVersionStatus.COMPLETED, ReportVersionStatus.FAILED],
        ReportVersionStatus.PARTIAL: [ReportVersionStatus.RUNNING, ReportVersionStatus.COMPLETED, ReportVersionStatus.FAILED],
    }
    
    if to_s not in allowed_transitions.get(from_s, []):
        return False, f"Invalid transition: {from_status} -> {to_status}"
    
    return True, "Transition allowed"


def can_transition_stage_attempt(
    from_status: str,
    to_status: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """Validate stage attempt status transition.
    
    Rules:
    - queued -> running
    - running -> succeeded | failed
    - succeeded and failed are terminal
    """
    try:
        from_s = StageAttemptStatus(from_status)
        to_s = StageAttemptStatus(to_status)
    except ValueError as e:
        return False, f"Invalid status value: {e}"
    
    if from_s == to_s:
        return False, "Cannot transition to the same status"
    
    # Terminal states
    if from_s in [StageAttemptStatus.SUCCEEDED, StageAttemptStatus.FAILED]:
        return False, f"Cannot transition from {from_status} (terminal state)"
    
    allowed_transitions = {
        StageAttemptStatus.QUEUED: [StageAttemptStatus.RUNNING],
        StageAttemptStatus.RUNNING: [StageAttemptStatus.SUCCEEDED, StageAttemptStatus.FAILED],
    }
    
    if to_s not in allowed_transitions.get(from_s, []):
        return False, f"Invalid transition: {from_status} -> {to_status}"
    
    return True, "Transition allowed"


def can_transition_export(
    from_status: str,
    to_status: str,
    context: Optional[Dict[str, Any]] = None
) -> Tuple[bool, str]:
    """Validate export status transition.
    
    Rules:
    - draft -> rendering
    - rendering -> ready | failed
    - ready -> delivered | failed
    - delivered is terminal
    """
    try:
        from_s = ExportStatus(from_status)
        to_s = ExportStatus(to_status)
    except ValueError as e:
        return False, f"Invalid status value: {e}"
    
    if from_s == to_s:
        return False, "Cannot transition to the same status"
    
    # Terminal state
    if from_s == ExportStatus.DELIVERED:
        return False, "Cannot transition from delivered (terminal state)"
    
    allowed_transitions = {
        ExportStatus.DRAFT: [ExportStatus.RENDERING],
        ExportStatus.RENDERING: [ExportStatus.READY, ExportStatus.FAILED],
        ExportStatus.READY: [ExportStatus.DELIVERED, ExportStatus.FAILED],
        ExportStatus.FAILED: [ExportStatus.RENDERING],  # Can retry
    }
    
    if to_s not in allowed_transitions.get(from_s, []):
        return False, f"Invalid transition: {from_status} -> {to_status}"
    
    return True, "Transition allowed"
