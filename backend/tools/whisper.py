from faster_whisper import WhisperModel
from backend.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


class WhisperTranscriber:
    """faster-whisper transcription service"""
    
    def __init__(self):
        logger.info(f"Loading Whisper model: {settings.whisper_model}")
        self.model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type
        )
        logger.info(f"Whisper model loaded successfully")
    
    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio file to text
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Transcribed text
        """
        logger.info(f"Transcribing audio: {audio_path}")
        
        segments, info = self.model.transcribe(
            audio_path,
            language="en",
            beam_size=5
        )
        
        # Collect all segments
        transcript_parts = []
        for segment in segments:
            transcript_parts.append(segment.text.strip())
        
        transcript = " ".join(transcript_parts)
        
        logger.info(f"Transcription complete. Language: {info.language}, "
                   f"Probability: {info.language_probability:.2f}, "
                   f"Length: {len(transcript)} chars")
        
        return transcript


# Singleton instance
_transcriber = None


def get_transcriber() -> WhisperTranscriber:
    """Get or create WhisperTranscriber instance"""
    global _transcriber
    if _transcriber is None:
        _transcriber = WhisperTranscriber()
    return _transcriber

# Made with Bob
