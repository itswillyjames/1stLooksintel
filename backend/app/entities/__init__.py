"""Entity resolution package."""

from app.entities.canonicalization import normalize_name, exact_match, fuzzy_match
from app.entities.extraction import extract_entities_from_report_version
from app.entities.merge_service import merge_entities, unmerge_entities

__all__ = [
    "normalize_name",
    "exact_match",
    "fuzzy_match",
    "extract_entities_from_report_version",
    "merge_entities",
    "unmerge_entities",
]
