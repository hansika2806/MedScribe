"""Application-wide constants for MedScribe"""

from backend.config import get_settings

settings = get_settings()

# Confidence Thresholds
CONFIDENCE_HIGH = settings.confidence_high
CONFIDENCE_MEDIUM = settings.confidence_medium

# File Upload Limits (in bytes)
MAX_AUDIO_SIZE_BYTES = settings.max_audio_size_mb * 1024 * 1024
MAX_PDF_SIZE_BYTES = settings.max_pdf_size_mb * 1024 * 1024

# Allowed file types
ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/webm",
    "audio/ogg",
}
ALLOWED_PDF_TYPES = {"application/pdf"}

# Audio validation
MIN_AUDIO_DURATION_SECONDS = 1.0
MAX_AUDIO_DURATION_SECONDS = 3600.0  # 1 hour

# Made with Bob
