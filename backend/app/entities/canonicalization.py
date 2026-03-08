"""Name canonicalization and matching for entity resolution."""

import re
from typing import Tuple

# Try to import rapidfuzz, fall back to simple matching if not available
try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


def normalize_name(name: str) -> str:
    """Normalize entity name for matching.
    
    Rules:
    1. Lowercase
    2. Remove punctuation except spaces
    3. Collapse multiple spaces
    4. Strip leading/trailing whitespace
    5. Remove common suffixes (inc, llc, co, corp, ltd) if safe
    
    Args:
        name: Raw entity name
    
    Returns:
        Normalized name (alias_norm)
    """
    if not name:
        return ""
    
    # Lowercase
    normalized = name.lower()
    
    # Remove punctuation except spaces (but keep hyphens temporarily)
    normalized = re.sub(r'[^a-z0-9\s\-]', ' ', normalized)
    
    # Collapse multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Strip
    normalized = normalized.strip()
    
    # Remove common business suffixes (safe removal)
    # Only remove if they appear as separate words at the end
    suffixes = ['inc', 'llc', 'co', 'corp', 'corporation', 'ltd', 'limited', 'company']
    words = normalized.split()
    
    # Remove trailing suffixes
    while words and words[-1] in suffixes:
        words.pop()
    
    normalized = ' '.join(words)
    
    return normalized


def exact_match(name1: str, name2: str) -> bool:
    """Check if two names are an exact match after normalization.
    
    Args:
        name1: First entity name
        name2: Second entity name
    
    Returns:
        True if normalized names are identical
    """
    return normalize_name(name1) == normalize_name(name2)


def fuzzy_match(name1: str, name2: str, threshold: float = 0.90) -> Tuple[bool, float]:
    """Check if two names are a fuzzy match.
    
    Uses token sort ratio from rapidfuzz if available, otherwise uses
    simple token Jaccard similarity.
    
    Args:
        name1: First entity name
        name2: Second entity name
        threshold: Minimum similarity score (0.0-1.0)
    
    Returns:
        (is_match, confidence_score)
    """
    norm1 = normalize_name(name1)
    norm2 = normalize_name(name2)
    
    # If exact match, return immediately
    if norm1 == norm2:
        return True, 1.0
    
    if RAPIDFUZZ_AVAILABLE:
        # Use rapidfuzz token sort ratio (accounts for word order)
        score = fuzz.token_sort_ratio(norm1, norm2) / 100.0
        return score >= threshold, score
    else:
        # Fallback: simple token Jaccard similarity
        tokens1 = set(norm1.split())
        tokens2 = set(norm2.split())
        
        if not tokens1 or not tokens2:
            return False, 0.0
        
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        
        score = len(intersection) / len(union) if union else 0.0
        return score >= threshold, score


def compute_match_confidence(name1: str, name2: str) -> float:
    """Compute match confidence between two names.
    
    Returns:
        Confidence score (0.0-1.0)
    """
    if exact_match(name1, name2):
        return 1.0
    
    is_match, confidence = fuzzy_match(name1, name2)
    return confidence
