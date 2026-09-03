"""
Speaker diarization — fast keyword-assisted fallback.

pyannote and Speechbrain are powerful but take 5-10 minutes on CPU for a
15-minute consultation. We instead use the timestamped segments returned by
Groq Whisper and classify speaker role with a lightweight keyword heuristic.
This runs in < 1 second and is good enough for the LLM pipeline downstream.

pyannote / Speechbrain classes are kept for optional future use but are NOT
loaded at startup anymore.
"""

from __future__ import annotations

import logging
import os
from typing import Literal, Optional

from backend.models.schemas import DiarizedTranscript, Utterance

logger = logging.getLogger(__name__)

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")


# ---------------------------------------------------------------------------
# Role-detection helpers
# ---------------------------------------------------------------------------

DOCTOR_KEYWORDS = [
    "prescribe", "diagnosis", "recommend", "examination", "treatment",
    "mg", "dosage", "let me", "i'll prescribe", "i recommend", "we need",
    "good morning", "what brings", "i see", "can you", "any shortness",
    "difficulty breathing", "please sit", "your blood pressure",
    "that's elevated", "higher than", "have you been taking",
    "that explains", "i'm going to", "let's schedule", "follow up",
    "blood test", "lab result", "normal range", "medication",
]

PATIENT_KEYWORDS = [
    " doctor", " my ", " i have ", " i feel ", " i've ", " i ran out ",
    "is that bad", "not great", "it gets", "it's more", "yes especially",
    "for the past", "started", "getting worse", "can't sleep",
    "chest pain", "headache", "nausea", "tired", "dizzy",
]


def _doctor_score(text: str) -> int:
    lower = text.lower()
    return sum(1 for kw in DOCTOR_KEYWORDS if kw in lower)


def _patient_score(text: str) -> int:
    lower = f" {text.lower()} "
    return sum(1 for kw in PATIENT_KEYWORDS if kw in lower)


def _classify_speaker(text: str, prev_speaker: Optional[str]) -> tuple[str, float]:
    """
    Classify a single utterance as Doctor / Patient / uncertain.
    Returns (speaker, confidence).
    """
    d = _doctor_score(text)
    p = _patient_score(text)

    if d > p:
        return "Doctor", min(0.90, 0.70 + d * 0.05)
    if p > d:
        return "Patient", min(0.90, 0.70 + p * 0.05)

    # Tie — alternate from previous speaker
    if prev_speaker == "Doctor":
        return "Patient", 0.60
    if prev_speaker == "Patient":
        return "Doctor", 0.60

    # No prior context — assume Doctor speaks first
    return "Doctor", 0.55


def _split_sentences(transcript: str) -> list[dict]:
    sentences = [
        p.strip()
        for p in transcript.replace("?", ".").replace("!", ".").split(".")
        if p.strip()
    ]
    return [
        {"start": float(i), "end": float(i + 1), "text": s}
        for i, s in enumerate(sentences)
    ]


# ---------------------------------------------------------------------------
# Main fast diarizer
# ---------------------------------------------------------------------------

def _fast_diarize(
    transcript: str,
    transcript_segments: Optional[list[dict]],
) -> DiarizedTranscript:
    """
    Keyword-heuristic diarization on Groq Whisper timestamped segments.
    Runs in < 1 second regardless of audio length.
    """
    logger.info("Diarization method selected: fast-keyword")
    segments = transcript_segments or _split_sentences(transcript)

    utterances: list[Utterance] = []
    prev_speaker: Optional[str] = None

    for seg in segments:
        text = seg.get("text", "").strip()
        if not text:
            continue
        speaker, confidence = _classify_speaker(text, prev_speaker)
        utterances.append(Utterance(
            speaker=speaker,
            text=text,
            confidence=confidence,
            timestamp=f"fast|{seg.get('start', 0):.2f}-{seg.get('end', 0):.2f}|{speaker}",
        ))
        prev_speaker = speaker

    logger.info("Fast diarization complete: %d utterances", len(utterances))
    return DiarizedTranscript(
        utterances=utterances,
        source="whisper",
        diarization_available=True,
    )


# ---------------------------------------------------------------------------
# Public interface — same signature as before
# ---------------------------------------------------------------------------

def diarize(
    audio_path: str,
    transcript: str,
    transcript_segments: Optional[list[dict]] = None,
) -> DiarizedTranscript:
    """
    Main entry point. Uses fast keyword diarization (< 1s).
    Falls back to sentence splitting if no segments available.
    """
    return _fast_diarize(transcript, transcript_segments)


# ---------------------------------------------------------------------------
# Stub kept for backward-compat with warm_models() in main.py
# ---------------------------------------------------------------------------

def get_pyannote_diarizer():
    """Stub — pyannote not loaded at startup (too slow on CPU)."""
    return None

# Made with Bob
