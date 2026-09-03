import logging
import os
import io

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class GroqWhisperTranscriber:
    """
    Fast transcription via Groq's Whisper API.
    Processes a 15-min audio in ~3 seconds vs ~90s local CPU.
    """

    def __init__(self):
        from groq import Groq
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = "whisper-large-v3-turbo"
        logger.info("GroqWhisperTranscriber ready (model: %s)", self.model)

    def transcribe_with_segments(self, audio_path: str) -> tuple[str, list[dict]]:
        """
        Transcribe audio via Groq API with verbose_json for timestamps.

        Returns:
            (transcript_text, list of {start, end, text} segment dicts)
        """
        logger.info("Transcribing via Groq API: %s", audio_path)

        with open(audio_path, "rb") as f:
            audio_bytes = f.read()

        # Use the filename so Groq can infer the codec
        filename = os.path.basename(audio_path)

        response = self.client.audio.transcriptions.create(
            model=self.model,
            file=(filename, audio_bytes),
            response_format="verbose_json",
            language="en",
            timestamp_granularities=["segment"],
        )

        # Build segment list from Groq verbose_json response
        segments = []
        if hasattr(response, "segments") and response.segments:
            for seg in response.segments:
                segments.append({
                    "start": float(seg.get("start", 0.0) if isinstance(seg, dict) else seg.start),
                    "end":   float(seg.get("end",   0.0) if isinstance(seg, dict) else seg.end),
                    "text":  (seg.get("text", "")  if isinstance(seg, dict) else seg.text).strip(),
                })

        transcript = response.text.strip() if hasattr(response, "text") else ""

        # Fallback: if no segments returned, split text into sentence chunks
        if not segments and transcript:
            sentences = [s.strip() for s in transcript.replace("?", ".").replace("!", ".").split(".") if s.strip()]
            for i, sentence in enumerate(sentences):
                segments.append({"start": float(i), "end": float(i + 1), "text": sentence})

        logger.info(
            "Groq transcription complete: %d chars, %d segments",
            len(transcript), len(segments),
        )
        return transcript, segments

    def transcribe(self, audio_path: str) -> str:
        transcript, _ = self.transcribe_with_segments(audio_path)
        return transcript


# ---------------------------------------------------------------------------
# Singleton — one instance shared for the lifetime of the process
# ---------------------------------------------------------------------------
_transcriber = None


def get_transcriber() -> GroqWhisperTranscriber:
    """Get or create the Groq transcriber singleton."""
    global _transcriber
    if _transcriber is None:
        _transcriber = GroqWhisperTranscriber()
    return _transcriber

# Made with Bob
