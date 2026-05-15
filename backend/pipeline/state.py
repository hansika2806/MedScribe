from typing import TypedDict, Optional, List, Dict, Any
from backend.models.schemas import (
    DiarizedTranscript,
    FilteredTranscript,
    ExtractedEntities,
    SOAPNote
)


class PipelineState(TypedDict, total=False):
    """State passed through LangGraph pipeline"""
    
    # Input
    audio_path: str
    pdf_path: str
    ocr_result: Dict[str, Any]
    ocr_method: str
    test_report_values: Dict[str, Any]
    
    # Transcription (Node 2 & 2b output)
    transcript_raw: Optional[str]
    transcript_diarized: Optional[DiarizedTranscript]
    
    # Filtering (Node 7 output - Clinical Relevance Filter)
    filtered_transcript: Optional[FilteredTranscript]
    
    # Extraction (Node 8 output - Clinical Extractor)
    extracted_entities: Optional[ExtractedEntities]
    
    # RAG (Node 10 output)
    retrieved_guidelines: List[Dict[str, Any]]
    
    # SOAP Generation (Node 11 output)
    soap_note: Optional[SOAPNote]
    
    # ICD-10 (Node 12 output)
    icd10_codes: List[Dict[str, str]]
    
    # QA Guardrail (Node 13 output)
    qa_result: Dict[str, Any]
    
    # Safety Guardrail (Node 14 output)
    safety_result: Dict[str, Any]
    
    # Review routing
    requires_physician_review: bool
    review_type: str
    review_message: str
    
    # Metadata
    session_id: str
    status: str
    error: Optional[str]
    diarization_method: str
    processing_time_seconds: float

# Made with Bob
