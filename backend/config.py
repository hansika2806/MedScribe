from pydantic_settings import BaseSettings
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Groq API
    groq_api_key: str
    llm_model: str = "llama-3.3-70b-versatile"
    guardrail_model: str = "llama-3.1-8b-instant"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048
    
    # Audio Processing
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    
    # Diarization (CRITICAL: Requires HuggingFace token)
    diarization_model: str = "pyannote/speaker-diarization-3.1"
    hf_token: str
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    # Security - JWT Authentication
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8
    
    # Demo Physician Credentials (Pre-hashed)
    dr_sharma_password_hash: str
    dr_sharma_name: str = "Dr. Priya Sharma"
    dr_sharma_department: str = "General Medicine"
    
    dr_kumar_password_hash: str
    dr_kumar_name: str = "Dr. Rahul Kumar"
    dr_kumar_department: str = "Cardiology"
    
    dr_patel_password_hash: str
    dr_patel_name: str = "Dr. Anjali Patel"
    dr_patel_department: str = "Endocrinology"
    
    # File Upload Limits
    max_audio_size_mb: int = 50
    max_pdf_size_mb: int = 10
    
    # CORS Configuration
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    
    # Confidence Thresholds
    confidence_high: float = 0.85
    confidence_medium: float = 0.70
    
    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    
    Returns:
        Settings: Application settings
    """
    settings = Settings()
    logger.info(f"Settings loaded: LLM={settings.llm_model}, "
                f"Guardrail LLM={settings.guardrail_model}, "
                f"Whisper={settings.whisper_model}, "
                f"Device={settings.whisper_device}")
    return settings

# Made with Bob
