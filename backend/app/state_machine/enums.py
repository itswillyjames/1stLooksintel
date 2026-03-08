"""Canonical status enums for all entities.

These are the single source of truth for valid status values.
"""

from enum import Enum


class PermitStatus(str, Enum):
    """Permit lifecycle status."""
    NEW = "new"
    NORMALIZED = "normalized"
    PREQUALIFIED = "prequalified"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class ReportStatus(str, Enum):
    """Report lifecycle status."""
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class ReportVersionStatus(str, Enum):
    """Report version lifecycle status."""
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    COMPLETED = "completed"
    FAILED = "failed"


class StageAttemptStatus(str, Enum):
    """Stage attempt lifecycle status."""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ExportStatus(str, Enum):
    """Export lifecycle status."""
    DRAFT = "draft"
    RENDERING = "rendering"
    READY = "ready"
    DELIVERED = "delivered"
    FAILED = "failed"
