from pydantic_settings import BaseSettings
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Groq API
    groq_api_key: str
    llm_model: str = "llama-3.3-70b-versatile"
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
                f"Whisper={settings.whisper_model}, "
                f"Device={settings.whisper_device}")
    return settings

# Made with Bob
