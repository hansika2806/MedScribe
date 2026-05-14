"""
Real speaker diarization using Speechbrain with fallback
Implements silence-based segmentation + speaker embedding clustering
"""
import logging
import numpy as np
from backend.models.schemas import Utterance, DiarizedTranscript
from typing import List, Optional, Tuple, Literal
import librosa
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import Speechbrain, sklearn, and torch
SpeakerRecognition = None
try:
    import torch

    try:
        from speechbrain.inference.speaker import SpeakerRecognition
        SPEECHBRAIN_IMPORT_PATH = "speechbrain.inference.speaker"
    except ImportError:
        from speechbrain.pretrained import SpeakerRecognition
        SPEECHBRAIN_IMPORT_PATH = "speechbrain.pretrained"

    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score
    SPEECHBRAIN_AVAILABLE = True
    logger.info(
        "Speechbrain available for real diarization "
        f"via {SPEECHBRAIN_IMPORT_PATH}"
    )
except ImportError as e:
    SPEECHBRAIN_AVAILABLE = False
    logger.warning(f"Speechbrain not available, will use fallback diarization: {e}")


class RealSpeakerDiarizer:
    """Real speaker diarization using Speechbrain embeddings"""
    
    def __init__(self):
        self.model = None
        if SPEECHBRAIN_AVAILABLE:
            try:
                # Load pretrained speaker recognition model
                self.model = SpeakerRecognition.from_hparams(
                    source="speechbrain/spkrec-ecapa-voxceleb",
                    savedir="data/models/speechbrain"
                )
                logger.info("Speechbrain model loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load Speechbrain model: {e}")
                self.model = None
    
    def segment_by_silence(self, audio_path: str, min_silence_len: float = 0.5) -> List[Tuple[float, float, np.ndarray]]:
        """
        Segment audio by silence detection
        
        Returns:
            List of (start_time, end_time, audio_segment) tuples
        """
        try:
            # Load audio
            y, sr = librosa.load(audio_path, sr=16000)
            
            # Detect non-silent intervals
            intervals = librosa.effects.split(
                y, 
                top_db=30,  # Silence threshold
                frame_length=2048,
                hop_length=512
            )
            
            segments = []
            for start_frame, end_frame in intervals:
                start_time = start_frame / sr
                end_time = end_frame / sr
                
                # Skip very short segments
                if end_time - start_time < 0.3:
                    continue
                
                audio_segment = y[start_frame:end_frame]
                segments.append((start_time, end_time, audio_segment))
            
            logger.info(f"Segmented audio into {len(segments)} segments")
            return segments
            
        except Exception as e:
            logger.error(f"Silence segmentation failed: {e}")
            return []
    
    def extract_embeddings(self, segments: List[tuple]) -> np.ndarray:
        """
        Extract speaker embeddings for each segment
        
        Returns:
            Array of shape (n_segments, embedding_dim)
        """
        embeddings = []
        
        for i, (start, end, audio) in enumerate(segments):
            try:
                # Speechbrain expects audio as numpy array
                # Extract embedding
                embedding = self.model.encode_batch(
                    torch.tensor(audio).unsqueeze(0)
                )
                embeddings.append(embedding.squeeze().cpu().numpy())
            except Exception as e:
                logger.warning(f"Failed to extract embedding for segment {i}: {e}")
                # Use zero embedding as fallback
                embeddings.append(np.zeros(192))  # ECAPA-TDNN embedding size
        
        return np.array(embeddings)
    
    def cluster_speakers(self, embeddings: np.ndarray, n_speakers: int = 2) -> Tuple[np.ndarray, float]:
        """
        Cluster embeddings into speaker labels
        
        Returns:
            Tuple of (labels array, confidence score)
        """
        try:
            clustering = AgglomerativeClustering(
                n_clusters=n_speakers,
                metric='cosine',
                linkage='average'
            )
            labels = clustering.fit_predict(embeddings)
            
            # Calculate cluster separation (confidence metric)
            confidence = silhouette_score(embeddings, labels, metric='cosine')
            confidence = (confidence + 1) / 2  # Normalize to 0-1
            
            logger.info(f"Clustering confidence: {confidence:.3f}")
            return labels, confidence
            
        except Exception as e:
            logger.error(f"Clustering failed: {e}")
            # Fallback: alternate labels
            return np.array([i % 2 for i in range(len(embeddings))]), 0.5
    
    def diarize(self, audio_path: str, transcript: str) -> Optional[DiarizedTranscript]:
        """
        Perform real speaker diarization
        
        Returns:
            DiarizedTranscript or None if failed
        """
        if not self.model:
            return None
        
        try:
            logger.info("Using Speechbrain diarization")
            
            # Segment audio by silence
            segments = self.segment_by_silence(audio_path)
            if not segments:
                logger.warning("No segments found")
                return None
            
            # Extract embeddings
            embeddings = self.extract_embeddings(segments)
            
            # Cluster into 2 speakers
            labels, confidence = self.cluster_speakers(embeddings, n_speakers=2)
            
            # Map labels to Doctor/Patient
            # Assume first speaker is Doctor
            speaker_map: dict[int, Literal["Doctor", "Patient"]] = {0: "Doctor", 1: "Patient"}
            
            # Split transcript into sentences
            sentences = [s.strip() for s in transcript.split(".") if s.strip()]
            
            # Align sentences with segments
            utterances: List[Utterance] = []
            for i, (start, end, _) in enumerate(segments):
                if i < len(sentences):
                    speaker = speaker_map[labels[i]]
                    utterances.append(Utterance(
                        speaker=speaker,
                        text=sentences[i],
                        confidence=float(confidence),
                        timestamp=f"{start:.2f}-{end:.2f}"
                    ))
            
            # Add remaining sentences if any
            for i in range(len(segments), len(sentences)):
                speaker = speaker_map[i % 2]
                utterances.append(Utterance(
                    speaker=speaker,
                    text=sentences[i],
                    confidence=float(confidence),
                    timestamp=str(i)
                ))
            
            logger.info(f"Speechbrain diarization complete: {len(utterances)} utterances")
            
            return DiarizedTranscript(
                utterances=utterances,
                source="whisper",  # Use valid literal
                diarization_available=True
            )
            
        except Exception as e:
            logger.error(f"Speechbrain diarization failed: {e}")
            return None


def fallback_diarize(transcript: str) -> DiarizedTranscript:
    """
    Simple fallback diarization that alternates speakers
    """
    logger.info("Using fallback diarization")
    
    # Split transcript into sentences
    sentences = [s.strip() for s in transcript.split(".") if s.strip()]
    
    utterances: List[Utterance] = []
    
    # Alternate between Doctor and Patient
    for i, sentence in enumerate(sentences):
        speaker = "Doctor" if i % 2 == 0 else "Patient"
        utterances.append(Utterance(
            speaker=speaker,
            text=sentence,
            confidence=0.70,
            timestamp=str(i)
        ))
    
    logger.info(f"Fallback diarization complete: {len(utterances)} utterances")
    
    return DiarizedTranscript(
        utterances=utterances,
        source="whisper",  # Use valid literal
        diarization_available=False
    )


# Global diarizer instance
_diarizer = None


def get_diarizer() -> Optional[RealSpeakerDiarizer]:
    """Get or create diarizer instance"""
    global _diarizer
    if _diarizer is None and SPEECHBRAIN_AVAILABLE:
        _diarizer = RealSpeakerDiarizer()
    return _diarizer


def diarize(audio_path: str, transcript: str) -> DiarizedTranscript:
    """
    Main diarization function with automatic fallback
    
    Tries Speechbrain first, falls back to alternating if it fails
    
    Args:
        audio_path: Path to audio file
        transcript: Raw transcript text from Whisper
        
    Returns:
        DiarizedTranscript with speaker labels
    """
    # Try real diarization first
    diarizer = get_diarizer()
    if diarizer:
        result = diarizer.diarize(audio_path, transcript)
        if result:
            return result
    
    # Fallback to alternating diarization
    return fallback_diarize(transcript)


# Made with Bob
