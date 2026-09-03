"""Custom exception classes for MedScribe application."""

from typing import Optional


class MedScribeException(Exception):
    """Base exception for all MedScribe errors."""
    
    def __init__(self, message: str, error_code: str = "UNKNOWN_ERROR", detail: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        self.detail = detail
        super().__init__(self.message)


class AuthenticationError(MedScribeException):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed", detail: Optional[str] = None):
        super().__init__(message, "AUTH_INVALID", detail)


class AuthorizationError(MedScribeException):
    """Raised when user lacks required permissions."""
    
    def __init__(self, message: str = "Insufficient permissions", detail: Optional[str] = None):
        super().__init__(message, "AUTH_EXPIRED", detail)


class ValidationError(MedScribeException):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message, "PIPELINE_VALIDATION_ERROR", detail)


class FileProcessingError(MedScribeException):
    """Raised when file processing fails."""
    
    def __init__(self, message: str, error_code: str, detail: Optional[str] = None):
        super().__init__(message, error_code, detail)


class TranscriptionError(FileProcessingError):
    """Raised when audio transcription fails."""
    
    def __init__(self, message: str = "Audio transcription failed", detail: Optional[str] = None):
        super().__init__(message, "WHISPER_FAILED", detail)


class DiarizationError(FileProcessingError):
    """Raised when speaker diarization fails."""
    
    def __init__(self, message: str = "Speaker diarization failed", detail: Optional[str] = None):
        super().__init__(message, "DIARIZATION_FAILED", detail)


class OCRError(FileProcessingError):
    """Raised when OCR processing fails."""
    
    def __init__(self, message: str = "OCR processing failed", detail: Optional[str] = None):
        super().__init__(message, "OCR_FAILED", detail)


class LLMError(MedScribeException):
    """Raised when LLM API calls fail."""
    
    def __init__(self, message: str = "LLM API error", detail: Optional[str] = None, is_rate_limit: bool = False):
        error_code = "GROQ_RATE_LIMIT" if is_rate_limit else "GROQ_API_ERROR"
        super().__init__(message, error_code, detail)


class PipelineError(MedScribeException):
    """Raised when pipeline processing fails."""
    
    def __init__(self, message: str, detail: Optional[str] = None):
        super().__init__(message, "PIPELINE_VALIDATION_ERROR", detail)


class DatabaseError(MedScribeException):
    """Raised when database operations fail."""
    
    def __init__(self, message: str = "Database operation failed", detail: Optional[str] = None):
        super().__init__(message, "DATABASE_ERROR", detail)


class ClinicalContentError(MedScribeException):
    """Raised when no clinical content can be extracted."""
    
    def __init__(self, message: str = "No clinical content found", detail: Optional[str] = None):
        super().__init__(message, "NO_CLINICAL_CONTENT", detail)


# Made with Bob