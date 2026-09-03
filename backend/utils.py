"""Shared utility functions for MedScribe"""

from typing import Any
import re


def plain_dict(value: Any) -> Any:
    """
    Convert Pydantic models to JSON-safe plain data.
    
    Args:
        value: Any value that might be a Pydantic model, dict, list, or primitive
        
    Returns:
        Plain dict/list/primitive representation
    """
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return {k: plain_dict(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain_dict(item) for item in value]
    return value


def scrub_phi(text: str, session_id: str = "REDACTED") -> str:
    """
    Scrub Protected Health Information from log messages.
    
    Args:
        text: Text that might contain PHI
        session_id: Session ID to keep for tracking
        
    Returns:
        Scrubbed text with PHI removed
    """
    if not text:
        return text
    
    # Keep session IDs
    scrubbed = text
    
    # Remove potential patient names (capitalized words)
    scrubbed = re.sub(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b', '[NAME]', scrubbed)
    
    # Remove phone numbers
    scrubbed = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', scrubbed)
    
    # Remove email addresses
    scrubbed = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', scrubbed)
    
    # Remove dates (various formats)
    scrubbed = re.sub(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', '[DATE]', scrubbed)
    
    # Remove addresses (basic pattern)
    scrubbed = re.sub(r'\b\d+\s+[A-Z][a-z]+\s+(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd)\b', '[ADDRESS]', scrubbed)
    
    return scrubbed


def validate_file_size(file_size: int, max_size: int, file_type: str) -> tuple[bool, str]:
    """
    Validate uploaded file size.
    
    Args:
        file_size: Size of file in bytes
        max_size: Maximum allowed size in bytes
        file_type: Type of file for error message
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if file_size == 0:
        return False, f"{file_type} file is empty"
    
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        actual_mb = file_size / (1024 * 1024)
        return False, f"{file_type} file size ({actual_mb:.1f}MB) exceeds maximum ({max_mb:.0f}MB)"
    
    return True, ""


# Made with Bob