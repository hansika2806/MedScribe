from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal, Union, Any
from datetime import datetime

# ============================================================================
# PROVENANCE MODELS
# ============================================================================

class ProvenanceRecord(BaseModel):
    """Provenance tracking for clinical entities"""
    source: Literal["transcript", "ocr", "both"]
    speaker: Literal["Patient", "Doctor", "ocr_system", "uncertain"]
    utterance: str
    verified: bool
    confidence: float = Field(ge=0.0, le=1.0)


# ============================================================================
# TRANSCRIPTION MODELS
# ============================================================================

class Utterance(BaseModel):
    """Single utterance from diarized transcript"""
    speaker: Literal["Doctor", "Patient", "uncertain"]
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: str


class DiarizedTranscript(BaseModel):
    """Complete diarized transcript"""
    utterances: List[Utterance]
    source: Literal["whisper", "manual_input"]
    diarization_available: bool


# ============================================================================
# FILTERED UTTERANCE MODELS
# ============================================================================

class FilteredUtterance(BaseModel):
    """Utterance after clinical relevance filtering"""
    speaker: Literal["Patient", "Doctor", "uncertain"]
    utterance: str
    included: bool
    maps_to: Optional[Literal["Subjective", "Objective", "Assessment", "Plan"]]
    reason: str
    speaker_uncertain: bool


class LabValueVerification(BaseModel):
    """Lab value cross-verification result"""
    lab_value: Optional[str] = None  # LLM returns this field name
    value: Optional[str] = None  # Alternative field name for compatibility
    source: Literal["both", "transcript_only", "ocr_only"]
    verified: bool
    flag: Optional[str] = None
    
    def __init__(self, **data):
        # If lab_value is provided but not value, copy it to value
        if 'lab_value' in data and 'value' not in data:
            data['value'] = data['lab_value']
        # If value is provided but not lab_value, copy it to lab_value
        elif 'value' in data and 'lab_value' not in data:
            data['lab_value'] = data['value']
        super().__init__(**data)


class FilteredTranscript(BaseModel):
    """Output from Clinical Relevance Filter"""
    filtered_utterances: List[FilteredUtterance]
    lab_value_verification: List[LabValueVerification]
    utterances_excluded_count: int
    speaker_uncertain_count: int


# ============================================================================
# CLINICAL ENTITY MODELS
# ============================================================================

class Symptom(BaseModel):
    """Patient-reported symptom"""
    symptom: str
    duration: Optional[str] = None
    source: str
    speaker: str
    utterance: str
    verified: bool


class Medication(BaseModel):
    """Medication with dosage"""
    drug: str
    dosage: Optional[str] = "unknown"
    frequency: Optional[str] = "unknown"
    source: str
    speaker: str
    utterance: str


class VitalSign(BaseModel):
    """Vital sign measurement"""
    value: str
    source: str
    speaker: str


class LabValue(BaseModel):
    """Laboratory test value"""
    value: str
    source: Literal["both", "transcript_only", "ocr_only"]
    verified: bool
    flag: Optional[str] = None
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    display_name: Optional[str] = None
    interpretation: Optional[str] = None


class FamilyHistory(BaseModel):
    """Family medical history"""
    condition: str
    relation: str
    source: str
    speaker: str


class PopulationTag(BaseModel):
    """Patient population classification"""
    age_group: Optional[str] = "adult"
    condition: str
    drug_class: str


class ExtractedEntities(BaseModel):
    """Output from Clinical Extractor"""
    symptoms: List[Symptom]
    medications: List[Medication]
    vitals: Dict[str, VitalSign]
    lab_values: Union[Dict[str, LabValue], Dict[str, Any]] = {}
    family_history: List[FamilyHistory]
    population_tag: PopulationTag


# ============================================================================
# SOAP NOTE MODELS
# ============================================================================

class SOAPEntity(BaseModel):
    """Entity within SOAP section with provenance"""
    claim: str
    source: str
    speaker: str
    utterance: str
    verified: bool
    confidence: float = Field(ge=0.0, le=1.0)


class UncertainSpan(BaseModel):
    """Uncertain portion of SOAP section"""
    text: str
    reason: str


class SOAPSection(BaseModel):
    """Single SOAP section"""
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    entities: List[SOAPEntity]
    uncertain_spans: List[UncertainSpan]


class AssessmentSection(SOAPSection):
    """Assessment section with diagnoses"""
    diagnoses: List[str]


class PlanSection(SOAPSection):
    """Plan section with guideline citations"""
    guideline_citations: List[str]


class SOAPNote(BaseModel):
    """Complete SOAP note"""
    subjective: SOAPSection
    objective: SOAPSection
    assessment: AssessmentSection
    plan: PlanSection


# ============================================================================
# API REQUEST/RESPONSE MODELS
# ============================================================================

class ConsultationRequest(BaseModel):
    """Request to start consultation processing"""
    audio_file: str = Field(description="Base64 encoded audio file")
    physician_id: str


class ConsultationResponse(BaseModel):
    """Response from consultation endpoint - Phase 2"""
    session_id: str
    status: Literal["processing", "completed", "failed"]
    message: str
    soap_note: Optional[SOAPNote] = None
    processing_time: Optional[float] = None
    
    # Phase 2 fields
    retrieved_guidelines: Optional[List[Dict[str, Any]]] = None
    qa_result: Optional[Dict[str, Any]] = None
    safety_result: Optional[Dict[str, Any]] = None
    requires_physician_review: Optional[bool] = None
    review_type: Optional[str] = None
    review_message: Optional[str] = None
    diarization_method: Optional[str] = None
    
    # Phase 3 persistence/review fields
    icd10_codes: Optional[List[Dict[str, Any]]] = None
    lab_values: Optional[List[Dict[str, Any]]] = None
    ocr_method: Optional[str] = None
    ocr_page_count: Optional[int] = None
    extracted_lab_values: Optional[Dict[str, Any]] = None
    approved: Optional[bool] = None
    approved_at: Optional[str] = None
    physician_username: Optional[str] = None
    patient_context: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None


class ConsultationStatus(BaseModel):
    """Status of consultation processing"""
    session_id: str
    status: Literal["processing", "completed", "failed"]
    soap_note: Optional[SOAPNote] = None
    confidence_scores: Optional[Dict[str, float]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

# Made with Bob
