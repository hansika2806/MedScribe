# MedScribe Phase 1 Implementation Plan

## Phase 1 Scope

**Goal**: Build a working FastAPI backend with basic audio transcription, clinical entity extraction, and SOAP note generation.

**What's IN Phase 1**:
- ✅ FastAPI backend foundation
- ✅ POST /consultation endpoint
- ✅ faster-whisper + pyannote-audio integration
- ✅ Clinical Relevance Filter (Agent 1)
- ✅ Clinical Extractor (Agent 2)
- ✅ Basic SOAP Generator
- ✅ Pydantic response models
- ✅ Basic LangGraph pipeline (simplified)

**What's OUT of Phase 1** (Future phases):
- ❌ PaddleOCR integration (test report reading)
- ❌ Hybrid RAG with ChromaDB
- ❌ QA and Safety Guardrails
- ❌ Human Handoff mechanisms
- ❌ Frontend React app
- ❌ Full 19-node pipeline

**Phase 1 Success Criteria**:
1. Audio file uploaded → transcribed with speaker labels
2. Clinical entities extracted with provenance
3. SOAP note generated with confidence scores
4. < 30 seconds processing time
5. Pydantic validation on all outputs

---

## Implementation Order

### **Step 1: Project Setup** (30 minutes)

#### 1.1 Create Directory Structure
```bash
medscribe/
├── backend/
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── graph.py
│   │   ├── state.py
│   │   └── nodes/
│   │       ├── __init__.py
│   │       ├── filter.py
│   │       ├── extractor.py
│   │       └── soap.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── whisper.py
│   │   └── diarization.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── llm.py
│   └── requirements.txt
├── data/
│   └── temp/
├── tests/
│   └── test_pipeline.py
├── .env.example
└── README.md
```

#### 1.2 Create requirements.txt
```txt
# Web Framework
fastapi==0.109.0
uvicorn[standard]==0.27.0
python-multipart==0.0.6

# Audio Processing
faster-whisper==0.10.0
pyannote-audio==3.1.1
torch==2.1.2
torchaudio==2.1.2

# LLM & Pipeline
groq==0.4.2
langgraph==0.0.26
langchain==0.1.0
langchain-core==0.1.10

# Data Models
pydantic==2.5.3
pydantic-settings==2.1.0

# Utilities
python-dotenv==1.0.0
```

#### 1.3 Create .env.example
```env
# Groq API
GROQ_API_KEY=your_groq_api_key_here

# Model Configuration
LLM_MODEL=llama-3.1-70b-versatile
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096

# Audio Processing
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

# Diarization
DIARIZATION_MODEL=pyannote/speaker-diarization-3.1
HF_TOKEN=your_huggingface_token_here

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True
```

---

### **Step 2: FastAPI Foundation** (45 minutes)

#### 2.1 Create [`backend/config.py`](backend/config.py)
```python
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # Groq API
    groq_api_key: str
    llm_model: str = "llama-3.1-70b-versatile"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 4096
    
    # Audio Processing
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    
    # Diarization
    diarization_model: str = "pyannote/speaker-diarization-3.1"
    hf_token: str
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
```

#### 2.2 Create [`backend/main.py`](backend/main.py)
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from backend.config import get_settings

settings = get_settings()

app = FastAPI(
    title="MedScribe API",
    description="Clinical Documentation AI",
    version="0.1.0",
    debug=settings.debug
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router, prefix="/api")

@app.get("/")
async def root():
    return {
        "message": "MedScribe API",
        "version": "0.1.0",
        "status": "running"
    }

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
```

---

### **Step 3: Pydantic Schemas** (30 minutes)

#### 3.1 Create [`backend/models/schemas.py`](backend/models/schemas.py)
```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Literal
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
    value: str
    source: Literal["both", "transcript_only", "ocr_only"]
    verified: bool
    flag: Optional[str] = None

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
    dosage: str
    frequency: str
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

class FamilyHistory(BaseModel):
    """Family medical history"""
    condition: str
    relation: str
    source: str
    speaker: str

class PopulationTag(BaseModel):
    """Patient population classification"""
    age_group: Literal["adult", "pediatric"]
    condition: str
    drug_class: str

class ExtractedEntities(BaseModel):
    """Output from Clinical Extractor"""
    symptoms: List[Symptom]
    medications: List[Medication]
    vitals: Dict[str, VitalSign]
    lab_values: Dict[str, LabValue]
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
    """Response from consultation endpoint"""
    session_id: str
    status: Literal["processing", "completed", "failed"]
    message: str
    soap_note: Optional[SOAPNote] = None
    processing_time: Optional[float] = None

class ConsultationStatus(BaseModel):
    """Status of consultation processing"""
    session_id: str
    status: Literal["processing", "completed", "failed"]
    soap_note: Optional[SOAPNote] = None
    confidence_scores: Optional[Dict[str, float]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
```

---

### **Step 4: Audio Processing Tools** (1 hour)

#### 4.1 Create [`backend/tools/whisper.py`](backend/tools/whisper.py)
```python
from faster_whisper import WhisperModel
from backend.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

class WhisperTranscriber:
    """faster-whisper transcription service"""
    
    def __init__(self):
        self.model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type
        )
        logger.info(f"Loaded Whisper model: {settings.whisper_model}")
    
    def transcribe(self, audio_path: str) -> str:
        """
        Transcribe audio file to text
        
        Args:
            audio_path: Path to audio file
            
        Returns:
            Transcribed text
        """
        segments, info = self.model.transcribe(
            audio_path,
            language="en",
            beam_size=5
        )
        
        transcript = " ".join([segment.text for segment in segments])
        
        logger.info(f"Transcription complete. Language: {info.language}, "
                   f"Probability: {info.language_probability:.2f}")
        
        return transcript

# Singleton instance
_transcriber = None

def get_transcriber() -> WhisperTranscriber:
    """Get or create WhisperTranscriber instance"""
    global _transcriber
    if _transcriber is None:
        _transcriber = WhisperTranscriber()
    return _transcriber
```

#### 4.2 Create [`backend/tools/diarization.py`](backend/tools/diarization.py)
```python
from pyannote.audio import Pipeline
from backend.config import get_settings
from backend.models.schemas import Utterance, DiarizedTranscript
import logging
from typing import List

logger = logging.getLogger(__name__)
settings = get_settings()

class SpeakerDiarizer:
    """pyannote-audio speaker diarization service"""
    
    def __init__(self):
        self.pipeline = Pipeline.from_pretrained(
            settings.diarization_model,
            use_auth_token=settings.hf_token
        )
        logger.info(f"Loaded diarization model: {settings.diarization_model}")
    
    def diarize(self, audio_path: str, transcript: str) -> DiarizedTranscript:
        """
        Perform speaker diarization on audio
        
        Args:
            audio_path: Path to audio file
            transcript: Raw transcript text
            
        Returns:
            DiarizedTranscript with speaker labels
        """
        # Run diarization
        diarization = self.pipeline(audio_path)
        
        # Split transcript into sentences
        sentences = transcript.split(". ")
        
        # Map sentences to speakers (simplified for Phase 1)
        utterances: List[Utterance] = []
        speaker_turns = list(diarization.itertracks(yield_label=True))
        
        for i, sentence in enumerate(sentences):
            if i < len(speaker_turns):
                turn, _, speaker = speaker_turns[i]
                # Map SPEAKER_XX to Doctor/Patient (simplified)
                speaker_label = "Doctor" if speaker.endswith("00") else "Patient"
                confidence = 0.85  # Simplified confidence
                
                utterances.append(Utterance(
                    speaker=speaker_label,
                    text=sentence.strip(),
                    confidence=confidence,
                    timestamp=f"{turn.start:.2f}"
                ))
        
        return DiarizedTranscript(
            utterances=utterances,
            source="whisper",
            diarization_available=True
        )

# Singleton instance
_diarizer = None

def get_diarizer() -> SpeakerDiarizer:
    """Get or create SpeakerDiarizer instance"""
    global _diarizer
    if _diarizer is None:
        _diarizer = SpeakerDiarizer()
    return _diarizer
```

---

### **Step 5: LLM Service** (30 minutes)

#### 5.1 Create [`backend/services/llm.py`](backend/services/llm.py)
```python
from groq import Groq
from backend.config import get_settings
import logging
from typing import Optional

logger = logging.getLogger(__name__)
settings = get_settings()

class LLMService:
    """Groq API client for LLM calls"""
    
    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.llm_model
        self.temperature = settings.llm_temperature
        self.max_tokens = settings.llm_max_tokens
        logger.info(f"Initialized Groq client with model: {self.model}")
    
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate completion from Groq API
        
        Args:
            system_prompt: System instruction
            user_prompt: User message
            temperature: Override default temperature
            max_tokens: Override default max tokens
            
        Returns:
            Generated text
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"Groq API error: {e}")
            raise

# Singleton instance
_llm_service = None

def get_llm_service() -> LLMService:
    """Get or create LLMService instance"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
```

---

### **Step 6: LangGraph Pipeline Nodes** (2 hours)

#### 6.1 Create [`backend/pipeline/state.py`](backend/pipeline/state.py)
```python
from typing import TypedDict, Optional
from backend.models.schemas import (
    DiarizedTranscript,
    FilteredTranscript,
    ExtractedEntities,
    SOAPNote
)

class PipelineState(TypedDict):
    """State passed through LangGraph pipeline"""
    # Input
    audio_path: str
    
    # Transcription
    transcript_raw: Optional[str]
    transcript_diarized: Optional[DiarizedTranscript]
    
    # Filtering
    filtered_transcript: Optional[FilteredTranscript]
    
    # Extraction
    extracted_entities: Optional[ExtractedEntities]
    
    # SOAP Generation
    soap_note: Optional[SOAPNote]
    
    # Metadata
    session_id: str
    status: str
    error: Optional[str]
```

#### 6.2 Create [`backend/pipeline/nodes/filter.py`](backend/pipeline/nodes/filter.py)
```python
from backend.pipeline.state import PipelineState
from backend.services.llm import get_llm_service
from backend.models.schemas import FilteredTranscript
import json
import logging

logger = logging.getLogger(__name__)

FILTER_SYSTEM_PROMPT = """ROLE:
You are the clinical relevance filter for MedScribe, processing raw diarized 
consultation transcripts before clinical extraction begins.

TASK:
Evaluate every utterance in the transcript. Mark each as included or excluded.

INCLUDE utterances containing:
- Patient-reported symptoms or complaints
- Duration or frequency of symptoms
- Medication names, dosages, or frequency
- Vital signs or numerical test values
- Family history of medical conditions
- Doctor clinical observations
- Doctor diagnoses or assessments
- Doctor prescriptions or treatment instructions

EXCLUDE utterances containing:
- Greetings or farewells
- Conversational filler phrases
- Scheduling or administrative content
- Repeated statements already captured
- Non-clinical small talk

For every included utterance: state which SOAP section it maps to and why.
For every excluded utterance: state exactly why.

OUTPUT FORMAT (JSON):
{
  "filtered_utterances": [
    {
      "speaker": "Patient",
      "utterance": "exact text",
      "included": true,
      "maps_to": "Subjective",
      "reason": "patient-reported symptom with duration",
      "speaker_uncertain": false
    }
  ],
  "lab_value_verification": [],
  "utterances_excluded_count": 0,
  "speaker_uncertain_count": 0
}"""

def clinical_relevance_filter(state: PipelineState) -> PipelineState:
    """
    Node: Clinical Relevance Filter (Agent 1)
    
    Determines which utterances are clinically relevant
    """
    logger.info("Running Clinical Relevance Filter...")
    
    transcript = state["transcript_diarized"]
    if not transcript:
        state["error"] = "No transcript available"
        return state
    
    # Format utterances for LLM
    utterances_text = "\n".join([
        f"[{u.speaker}]: {u.text} (confidence: {u.confidence:.2f})"
        for u in transcript.utterances
    ])
    
    user_prompt = f"Raw transcript:\n{utterances_text}"
    
    # Call LLM
    llm = get_llm_service()
    response = llm.generate(FILTER_SYSTEM_PROMPT, user_prompt)
    
    # Parse JSON response
    try:
        filtered_data = json.loads(response)
        state["filtered_transcript"] = FilteredTranscript(**filtered_data)
        logger.info(f"Filtered {len(filtered_data['filtered_utterances'])} utterances")
    except Exception as e:
        logger.error(f"Failed to parse filter response: {e}")
        state["error"] = str(e)
    
    return state
```

#### 6.3 Create [`backend/pipeline/nodes/extractor.py`](backend/pipeline/nodes/extractor.py)
```python
from backend.pipeline.state import PipelineState
from backend.services.llm import get_llm_service
from backend.models.schemas import ExtractedEntities
import json
import logging

logger = logging.getLogger(__name__)

EXTRACTOR_SYSTEM_PROMPT = """ROLE:
You are the clinical NLP extraction agent for MedScribe.

TASK:
From the filtered transcript, extract all clinically relevant entities with 
full provenance for each entity.

1. SYMPTOMS — from Patient turns only
2. MEDICATIONS — from Doctor turns only
3. VITAL SIGNS — from Doctor turns
4. LAB VALUES — from Doctor turns
5. FAMILY HISTORY — from Patient turns only
6. POPULATION TAG — age_group, condition, drug_class

OUTPUT FORMAT (JSON):
{
  "symptoms": [
    {
      "symptom": "chest pain",
      "duration": "3 days",
      "source": "transcript",
      "speaker": "Patient",
      "utterance": "My chest has been hurting for 3 days",
      "verified": true
    }
  ],
  "medications": [],
  "vitals": {},
  "lab_values": {},
  "family_history": [],
  "population_tag": {
    "age_group": "adult",
    "condition": "unknown",
    "drug_class": "none"
  }
}

CONSTRAINTS:
- Extract only what was explicitly stated
- Symptoms from patient turns only
- Prescriptions from doctor turns only
- Every entity carries source, speaker, utterance reference"""

def clinical_extractor(state: PipelineState) -> PipelineState:
    """
    Node: Clinical Extractor (Agent 2)
    
    Extracts structured clinical entities with provenance
    """
    logger.info("Running Clinical Extractor...")
    
    filtered = state["filtered_transcript"]
    if not filtered:
        state["error"] = "No filtered transcript available"
        return state
    
    # Format filtered utterances for LLM
    included_utterances = [
        u for u in filtered.filtered_utterances if u.included
    ]
    
    utterances_text = "\n".join([
        f"[{u.speaker}]: {u.utterance} (maps to: {u.maps_to})"
        for u in included_utterances
    ])
    
    user_prompt = f"Filtered transcript:\n{utterances_text}"
    
    # Call LLM
    llm = get_llm_service()
    response = llm.generate(EXTRACTOR_SYSTEM_PROMPT, user_prompt)
    
    # Parse JSON response
    try:
        entities_data = json.loads(response)
        state["extracted_entities"] = ExtractedEntities(**entities_data)
        logger.info(f"Extracted {len(entities_data['symptoms'])} symptoms, "
                   f"{len(entities_data['medications'])} medications")
    except Exception as e:
        logger.error(f"Failed to parse extractor response: {e}")
        state["error"] = str(e)
    
    return state
```

#### 6.4 Create [`backend/pipeline/nodes/soap.py`](backend/pipeline/nodes/soap.py)
```python
from backend.pipeline.state import PipelineState
from backend.services.llm import get_llm_service
from backend.models.schemas import SOAPNote
import json
import logging

logger = logging.getLogger(__name__)

SOAP_SYSTEM_PROMPT = """ROLE:
You are the clinical documentation specialist for MedScribe, generating 
structured SOAP notes.

TASK:
Using extracted clinical entities, generate a complete SOAP note with full 
entity-level provenance.

S — SUBJECTIVE:
Patient-reported symptoms and duration.

O — OBJECTIVE:
Vitals and lab values.

A — ASSESSMENT:
Clinical diagnosis based on S and O data.

P — PLAN:
Treatment plan.

CONFIDENCE SCORING:
Assign confidence score 0-1 to each section.

OUTPUT FORMAT (JSON):
{
  "subjective": {
    "content": "Patient reports...",
    "confidence": 0.92,
    "entities": [
      {
        "claim": "chest pain for 3 days",
        "source": "transcript",
        "speaker": "Patient",
        "utterance": "My chest hurting for 3 days",
        "verified": true,
        "confidence": 0.95
      }
    ],
    "uncertain_spans": []
  },
  "objective": {...},
  "assessment": {
    "content": "...",
    "diagnoses": ["Type 2 Diabetes"],
    "confidence": 0.90,
    "entities": [],
    "uncertain_spans": []
  },
  "plan": {
    "content": "...",
    "guideline_citations": [],
    "confidence": 0.85,
    "entities": [],
    "uncertain_spans": []
  }
}

CONSTRAINTS:
- All four sections mandatory
- Never fabricate data not present in input
- Every entity must carry full provenance record"""

def soap_generator(state: PipelineState) -> PipelineState:
    """
    Node: SOAP Note Generator
    
    Generates structured SOAP note with provenance
    """
    logger.info("Running SOAP Generator...")
    
    entities = state["extracted_entities"]
    if not entities:
        state["error"] = "No extracted entities available"
        return state
    
    # Format entities for LLM
    entities_text = f"""
Symptoms: {json.dumps([s.dict() for s in entities.symptoms], indent=2)}
Medications: {json.dumps([m.dict() for m in entities.medications], indent=2)}
Vitals: {json.dumps({k: v.dict() for k, v in entities.vitals.items()}, indent=2)}
Lab Values: {json.dumps({k: v.dict() for k, v in entities.lab_values.items()}, indent=2)}
Family History: {json.dumps([f.dict() for f in entities.family_history], indent=2)}
"""
    
    user_prompt = f"Clinical entities:\n{entities_text}"
    
    # Call LLM
    llm = get_llm_service()
    response = llm.generate(SOAP_SYSTEM_PROMPT, user_prompt)
    
    # Parse JSON response
    try:
        soap_data = json.loads(response)
        state["soap_note"] = SOAPNote(**soap_data)
        logger.info("SOAP note generated successfully")
    except Exception as e:
        logger.error(f"Failed to parse SOAP response: {e}")
        state["error"] = str(e)
    
    return state
```

---

### **Step 7: LangGraph Pipeline** (45 minutes)

#### 7.1 Create [`backend/pipeline/graph.py`](backend/pipeline/graph.py)
```python
from langgraph.graph import StateGraph, END
from backend.pipeline.state import PipelineState
from backend.pipeline.nodes.filter import clinical_relevance_filter
from backend.pipeline.nodes.extractor import clinical_extractor
from backend.pipeline.nodes.soap import soap_generator
from backend.tools.whisper import get_transcriber
from backend.tools.diarization import get_diarizer
import logging

logger = logging.getLogger(__name__)

def transcribe_node(state: PipelineState) -> PipelineState:
    """Node: Transcribe audio with faster-whisper"""
    logger.info("Transcribing audio...")
    transcriber = get_transcriber()
    state["transcript_raw"] = transcriber.transcribe(state["audio_path"])
    return state

def diarize_node(state: PipelineState) -> PipelineState:
    """Node: Diarize audio with pyannote-audio"""
    logger.info("Diarizing audio...")
    diarizer = get_diarizer()
    state["transcript_diarized"] = diarizer.diarize(
        state["audio_path"],
        state["transcript_raw"]
    )
    return state

def build_pipeline() -> StateGraph:
    """
    Build Phase 1 LangGraph pipeline
    
    Flow:
    1. Transcribe (faster-whisper)
    2. Diarize (pyannote-audio)
    3. Filter (Clinical Relevance Filter)
    4. Extract (Clinical Extractor)
    5. Generate SOAP (SOAP Generator)
    """
    workflow = StateGraph(PipelineState)
    
    # Add nodes
    workflow.add_node("transcribe", transcribe_node)
    workflow.add_node("diarize", diarize_node)
    workflow.add_node("filter", clinical_relevance_filter)
    workflow.add_node("extract", clinical_extractor)
    workflow.add_node("soap", soap_generator)
    
    # Define edges
    workflow.set_entry_point("transcribe")
    workflow.add_edge("transcribe", "diarize")
    workflow.add_edge("diarize", "filter")
    workflow.add_edge("filter", "extract")
    workflow.add_edge("extract", "soap")
    workflow.add_edge("soap", END)
    
    return workflow.compile()

# Singleton instance
_pipeline = None

def get_pipeline() -> StateGraph:
    """Get or create pipeline instance"""
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
        logger.info("Pipeline built successfully")
    return _pipeline
```

---

### **Step 8: API Routes** (30 minutes)

#### 8.1 Create [`backend/api/routes.py`](backend/api/routes.py)
```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.models.schemas import ConsultationResponse
from backend.pipeline.graph import get_pipeline
from backend.pipeline.state import PipelineState
import uuid
import base64
import logging
from pathlib import Path
import time

logger = logging.getLogger(__name__)
router = APIRouter()

TEMP_DIR = Path("data/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

@router.post("/consultation", response_model=ConsultationResponse)
async def create_consultation(audio_file: UploadFile = File(...)):
    """
    Process consultation audio and generate SOAP note
    
    Phase 1: Simplified endpoint that processes immediately
    """
    session_id = str(uuid.uuid4())
    
    try:
        # Save uploaded audio file
        audio_path = TEMP_DIR / f"{session_id}.wav"
        with open(audio_path, "wb") as f:
            f.write(await audio_file.read())
        
        logger.info(f"Processing consultation {session_id}")
        start_time = time.time()
        
        # Initialize state
        initial_state: PipelineState = {
            "audio_path": str(audio_path),
            "transcript_raw": None,
            "transcript_diarized": None,
            "filtered_transcript": None,
            "extracted_entities": None,
            "soap_note": None,
            "session_id": session_id,
            "status": "processing",
            "error": None
        }
        
        # Run pipeline
        pipeline = get_pipeline()
        final_state = pipeline.invoke(initial_state)
        
        processing_time = time.time() - start_time
        
        # Check for errors
        if final_state.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Pipeline error: {final_state['error']}"
            )
        
        # Clean up temp file
        audio_path.unlink()
        
        logger.info(f"Consultation {session_id} completed in {processing_time:.2f}s")
        
        return ConsultationResponse(
            session_id=session_id,
            status="completed",
            message="SOAP note generated successfully",
            soap_note=final_state["soap_note"],
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Error processing consultation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/consultation/{session_id}")
async def get_consultation(session_id: str):
    """Get consultation status (placeholder for Phase 1)"""
    return {
        "session_id": session_id,
        "status": "not_implemented",
        "message": "Status endpoint will be implemented in future phase"
    }
```

---

### **Step 9: Testing** (30 minutes)

#### 9.1 Create [`tests/test_pipeline.py`](tests/test_pipeline.py)
```python
import pytest
from backend.pipeline.graph import build_pipeline
from backend.pipeline.state import PipelineState

def test_pipeline_structure():
    """Test that pipeline builds correctly"""
    pipeline = build_pipeline()
    assert pipeline is not None

def test_pipeline_nodes():
    """Test that all nodes are present"""
    pipeline = build_pipeline()
    nodes = pipeline.nodes
    
    assert "transcribe" in nodes
    assert "diarize" in nodes
    assert "filter" in nodes
    assert "extract" in nodes
    assert "soap" in nodes

# Add more tests as needed
```

---

## Phase 1 Testing Plan

### Manual Testing Steps

1. **Start the server**:
```bash
cd backend
python main.py
```

2. **Test health endpoint**:
```bash
curl http://localhost:8000/health
```

3. **Test consultation endpoint** (with sample audio):
```bash
curl -X POST http://localhost:8000/api/consultation \
  -F "audio_file=@sample_consultation.wav"
```

4. **Verify response**:
- Check SOAP note structure
- Verify confidence scores
- Check provenance records
- Confirm processing time < 30 seconds

---

## Phase 1 Success Checklist

- [ ] FastAPI server starts without errors
- [ ] Health endpoint returns 200
- [ ] Audio file uploads successfully
- [ ] faster-whisper transcribes audio
- [ ] pyannote-audio diarizes speakers
- [ ] Clinical Relevance Filter runs
- [ ] Clinical Extractor extracts entities
- [ ] SOAP Generator produces note
- [ ] Response includes all SOAP sections
- [ ] Confidence scores present
- [ ] Provenance records attached
- [ ] Processing time < 30 seconds
- [ ] Pydantic validation passes

---

## Next Steps After Phase 1

Once Phase 1 is complete and tested:

1. **Phase 2**: Add PaddleOCR for test report reading
2. **Phase 3**: Implement ChromaDB RAG for guidelines
3. **Phase 4**: Add QA and Safety Guardrails
4. **Phase 5**: Build Human Handoff mechanisms
5. **Phase 6**: Create React frontend
6. **Phase 7**: Complete full 19-node pipeline

---

## Estimated Timeline

- **Step 1** (Project Setup): 30 minutes
- **Step 2** (FastAPI Foundation): 45 minutes
- **Step 3** (Pydantic Schemas): 30 minutes
- **Step 4** (Audio Processing): 1 hour
- **Step 5** (LLM Service): 30 minutes
- **Step 6** (Pipeline Nodes): 2 hours
- **Step 7** (LangGraph Pipeline): 45 minutes
- **Step 8** (API Routes): 30 minutes
- **Step 9** (Testing): 30 minutes

**Total**: ~7 hours for Phase 1 implementation

---

This plan provides a clear, step-by-step path to building the Phase 1 MVP of MedScribe.