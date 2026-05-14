# MedScribe Architecture Plan

## Executive Summary

MedScribe is a clinical documentation AI that captures doctor-patient consultations via audio and test report PDFs simultaneously, processes them through a LangGraph multi-agent pipeline, and generates structured SOAP notes with full provenance tracking for physician review and approval.

**Core Innovation**: One-button documentation flow that captures conversation and test data simultaneously, with utterance-level clinical relevance filtering and entity-level provenance tracking.

**Design Principle**: Copilot, not autopilot. Every note requires explicit physician approval. No automated saving.

---

## Technology Stack (100% Free & Local)

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| **LLM** | Groq API + Llama 3.1 70B | Free tier, fast inference, medical reasoning capability |
| **Speech-to-Text** | faster-whisper | Local, free, GPU-accelerated, production-grade |
| **Speaker Diarization** | pyannote-audio | Free HuggingFace model, speaker attribution |
| **OCR** | PaddleOCR | Local, free, handles medical documents well |
| **RAG Database** | ChromaDB | Local vector store, free, easy setup |
| **Pipeline** | LangGraph (self-hosted) | Free, state management, conditional routing |
| **Session State** | LangGraph in-memory | Free, cleared after consultation |
| **SOAP Storage** | SQLite | Local, free, sufficient for single-physician use |
| **Backend** | FastAPI + Python 3.11 | Fast, async, type-safe |
| **Frontend** | React + Tailwind CSS | Modern, responsive, component-based |

**Cost Target**: Rs. 0/month for compute (all local) + potential Groq API costs if exceeding free tier

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         MEDSCRIBE SYSTEM                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐                    ┌──────────────┐          │
│  │   Frontend   │◄──────REST API────►│   Backend    │          │
│  │ React + TW   │                    │   FastAPI    │          │
│  └──────────────┘                    └──────┬───────┘          │
│                                              │                   │
│                                              ▼                   │
│                                    ┌─────────────────┐          │
│                                    │  LangGraph      │          │
│                                    │  Pipeline       │          │
│                                    │  (19 Nodes)     │          │
│                                    └─────────────────┘          │
│                                              │                   │
│         ┌────────────────┬─────────────────┼─────────────┐     │
│         ▼                ▼                  ▼             ▼     │
│  ┌──────────┐    ┌──────────┐      ┌──────────┐  ┌──────────┐│
│  │ faster-  │    │ pyannote │      │ PaddleOCR│  │ ChromaDB ││
│  │ whisper  │    │  -audio  │      │          │  │   RAG    ││
│  └──────────┘    └──────────┘      └──────────┘  └──────────┘│
│                                                                  │
│                         ┌──────────┐                            │
│                         │  SQLite  │                            │
│                         │  SOAP DB │                            │
│                         └──────────┘                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## The 19-Node LangGraph Pipeline

### **Phase 1: Parallel Input Capture**

#### Node 1: INPUT
- **Type**: Entry Point
- **Function**: Doctor presses record once. Two parallel processes launch simultaneously.
- **Outputs**: 
  - `audio_stream` → Node 2 (Whisper)
  - `screen_capture` → Node 3 (PaddleOCR)

#### Node 2: TOOL CALL — faster-whisper STT
- **Type**: Tool Call
- **Tool**: faster-whisper (local)
- **Input**: `audio_stream`
- **Output**: `transcript_raw`
- **Function**: Real-time speech-to-text transcription
- **Next**: Node 4 (Transcription Fallback)

#### Node 3: TOOL CALL — PaddleOCR
- **Type**: Tool Call
- **Tool**: PaddleOCR (local)
- **Input**: `screen_capture` (active PDF on screen)
- **Output**: `test_report_values`
- **Function**: Extract numerical lab values from test report PDF
- **Next**: Node 5 (OCR Fallback)

---

### **Phase 2: Fallback & Diarization**

#### Node 4: RETRY/FALLBACK — Transcription
- **Type**: Retry/Fallback
- **Max Retries**: 2 (500ms, 1000ms backoff)
- **Fallback**: Manual text input mode
- **Output**: Structured signal (never null)
  ```json
  {
    "transcript": "<text>",
    "source": "whisper|manual_input",
    "diarization_available": true|false
  }
  ```
- **Next**: Node 6 (Merge/Join)

**Critical**: If faster-whisper fails, switch to manual input. Pipeline continues. Only transcription method replaced, not entire flow.

#### Node 5: RETRY/FALLBACK — OCR
- **Type**: Retry/Fallback
- **Max Retries**: 2 (500ms, 1000ms backoff)
- **Fallback**: Structured unavailable signal
- **Output**: 
  ```json
  {
    "test_values": "unavailable",
    "reason": "pdf_read_failure",
    "action": "physician_manual_entry"
  }
  ```
- **Next**: Node 6 (Merge/Join)

**Critical**: OCR failure = partial degradation, not full replacement. Gap marked explicitly and carried forward.

#### Node 2b: TOOL CALL — pyannote-audio Diarization
- **Type**: Tool Call (runs after Node 4 if transcription succeeded)
- **Tool**: pyannote-audio
- **Input**: `audio_stream` + `transcript_raw`
- **Output**: `transcript_diarized`
- **Function**: Label each utterance as [Doctor] or [Patient] with confidence score
- **Format**:
  ```json
  {
    "utterances": [
      {
        "speaker": "Doctor",
        "text": "How long have you had this pain?",
        "confidence": 0.92,
        "timestamp": "00:00:05"
      },
      {
        "speaker": "Patient", 
        "text": "About three days. Gets worse at night.",
        "confidence": 0.88,
        "timestamp": "00:00:08"
      }
    ]
  }
  ```
- **Next**: Node 6 (Merge/Join)

---

### **Phase 3: Merge & Filter**

#### Node 6: MERGE/JOIN
- **Type**: Merge/Join
- **Function**: Wait for both parallel branches (transcription + OCR) to complete
- **Input**: 
  - `transcript_diarized` (or manual input signal)
  - `test_report_values` (or unavailable signal)
- **Output**: Single unified consultation input
- **Next**: Node 7 (Clinical Relevance Filter)

#### Node 7: LLM STEP — Clinical Relevance Filter (Agent 1)
- **Type**: LLM Step
- **Model**: Groq + Llama 3.1 70B
- **Function**: Determine which utterances are clinically relevant
- **Process**:
  1. **Relevance Filtering**: Evaluate every utterance
     - INCLUDE: symptoms, medications, vitals, diagnoses, prescriptions
     - EXCLUDE: greetings, filler, scheduling, small talk
     - Every inclusion/exclusion has explicit reason
  2. **Speaker Attribution Check**: 
     - If speaker confidence < 0.80 → mark `speaker_uncertain: true`
     - Exclude from extraction, flag for manual review
  3. **Lab Value Cross-Verification**:
     - Compare verbal mentions against OCR values
     - If match → `verified: true, source: both`
     - If no match → `verified: false, flag: "verbally mentioned but not confirmed"`

- **Output**:
  ```json
  {
    "filtered_utterances": [
      {
        "speaker": "Patient",
        "utterance": "My chest has been hurting for 3 days",
        "included": true,
        "maps_to": "Subjective",
        "reason": "patient-reported symptom with duration",
        "speaker_uncertain": false
      }
    ],
    "lab_value_verification": [
      {
        "value": "HbA1c 8.2%",
        "source": "both",
        "verified": true
      }
    ],
    "utterances_excluded_count": 12,
    "speaker_uncertain_count": 2
  }
  ```

- **Next**: Node 8 (Clinical Extractor)

**Innovation**: This node is absent from standard clinical documentation workflows. It's the key differentiator in pre-extraction quality control.

---

### **Phase 4: Extraction & Context**

#### Node 8: LLM STEP — Clinical Extractor (Agent 2)
- **Type**: LLM Step
- **Model**: Groq + Llama 3.1 70B
- **Function**: Extract structured clinical entities with full provenance
- **Extraction Categories**:
  1. **Symptoms** (from Patient turns only)
  2. **Medications** (from Doctor turns only)
  3. **Vital Signs** (from Doctor or OCR)
  4. **Lab Values** (from OCR, verified)
  5. **Family History** (from Patient turns only)
  6. **Population Tag** (age_group, condition, drug_class)

- **Output**:
  ```json
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
    "medications": [...],
    "vitals": {
      "BP": "148/92",
      "source": "transcript",
      "speaker": "Doctor"
    },
    "lab_values": {
      "HbA1c": {
        "value": "8.2%",
        "source": "both",
        "verified": true,
        "flag": null
      }
    },
    "population_tag": {
      "age_group": "adult",
      "condition": "diabetes, hypertension",
      "drug_class": "antidiabetic"
    }
  }
  ```

- **Next**: Node 9 (Session Context Store)

**Critical**: Every entity carries source, speaker, utterance reference. Never fabricate lab values when OCR unavailable.

#### Node 9: MEMORY/CONTEXT — Session Context Store
- **Type**: Memory/Context
- **Storage**: LangGraph in-memory state
- **Scope**: Intra-session only (cleared after consultation)
- **Function**: Store Agent 2 extraction output for two downstream agents
- **Readers**:
  - Agent 3 (Knowledge Retrieval) → reads `population_tag`
  - Agent 4 (QA Guardrail) → reads all extracted entities
- **Next**: 
  - Node 10 (Hybrid RAG)
  - Node 13 (QA Guardrail) — direct connection

---

### **Phase 5: Knowledge Retrieval**

#### Node 10: KNOWLEDGE RETRIEVAL — Hybrid RAG (Agent 3)
- **Type**: Knowledge Retrieval
- **Database**: ChromaDB (local vector store)
- **Corpus**: 
  - ADA Guidelines (American Diabetes Association)
  - WHO Protocols
  - ICD-10 reference tables
  - PubMed clinical summaries
  - All documents metadata-tagged: population, condition, drug_class, year

- **Retrieval Method**: Hybrid scoring
  ```
  Score = α × Cosine Similarity + β × BM25 + γ × Metadata Match
  ```
  
  Where:
  - **Cosine Similarity**: Semantic vector similarity
  - **BM25**: Keyword frequency relevance
  - **Metadata Match**: Hard pre-filter by population_tag
    - `age_group` (adult/pediatric)
    - `condition` (diabetes, hypertension, etc.)
    - `drug_class` (antidiabetic, antihypertensive, etc.)

- **Critical Innovation**: γ × Metadata Match operates as hard pre-filter. Guidelines not matching patient population are **excluded entirely** before scoring begins. Adult diabetes guidelines never retrieved for pediatric patients.

- **Output**:
  ```json
  {
    "retrieved_guidelines": [
      {
        "content": "For adults with T2DM and HbA1c >7%, increase metformin...",
        "source": "ADA 2024 §6.5",
        "relevance_score": 0.89,
        "population_match": "adult, diabetes, antidiabetic",
        "guideline_year": 2024
      }
    ]
  }
  ```

- **Next**: Node 11 (SOAP Generator)

---

### **Phase 6: SOAP Generation**

#### Node 11: LLM STEP — SOAP Note Generator
- **Type**: LLM Step
- **Model**: Groq + Llama 3.1 70B
- **Function**: Generate structured SOAP note with full provenance
- **Input**: 
  - Extracted entities from Session Context Store
  - Retrieved guidelines from Agent 3

- **SOAP Structure**:

  **S — SUBJECTIVE**:
  - Patient-reported symptoms and duration
  - Source: Patient turns only
  - If diarization unavailable: note explicitly

  **O — OBJECTIVE**:
  - Vitals and lab values
  - If lab values pending: "Lab values pending physician input"
  - Unverified values carry flag

  **A — ASSESSMENT**:
  - Clinical diagnosis based on S and O
  - Informed by retrieved guidelines
  - Diagnosis names only (ICD-10 codes added by next node)

  **P — PLAN**:
  - Treatment plan
  - Every recommendation cites guideline source
  - Format: "Recommendation. (Source: ADA 2024 §X.X)"

- **Confidence Scoring**: Each section gets 0-1 score
  - Below 0.85: list specific uncertain spans with reason

- **Provenance Record**: Every entity includes:
  - `source`: transcript / ocr / both
  - `speaker`: Patient / Doctor / ocr_system
  - `utterance`: exact original text
  - `verified`: true / false
  - `confidence`: entity-level score

- **Output**:
  ```json
  {
    "subjective": {
      "content": "Patient reports chest pain for 3 days, worsening when lying down...",
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
    "assessment": {...},
    "plan": {...}
  }
  ```

- **Next**: Node 12 (ICD-10 Mapper)

---

### **Phase 7: ICD-10 Mapping**

#### Node 12: TOOL CALL — ICD-10 Mapper
- **Type**: Tool Call
- **API**: ICD-10 CDC API (free US government API)
- **Input**: `assessment_diagnoses`
- **Function**: Map each diagnosis to current official ICD-10 code
- **Rationale**: LLM training data may contain outdated codes. ICD-10 updates annually. Using external API guarantees current code accuracy.

- **Example**:
  - Input: "Type 2 Diabetes — uncontrolled"
  - Output: "E11.65"
  - Input: "Essential Hypertension"
  - Output: "I10"

- **Next**: Node 13 (QA Guardrail)

---

### **Phase 8: Quality Assurance**

#### Node 13: EVALUATOR/GUARDRAIL — QA Agent (Agent 4)
- **Type**: Evaluator/Guardrail
- **Model**: Groq + Llama 3.1 70B
- **Function**: Validate SOAP note for completeness, accuracy, provenance integrity

- **Five Documentation Quality Checks**:

  **1. MISSING FIELDS**:
  - All four SOAP sections present and non-empty?
  - If any empty → FLAG

  **2. POPULATION MISMATCH**:
  - Compare `population_tag` from Session Context against guideline sources in Plan
  - If mismatch → FLAG

  **3. LOW CONFIDENCE SECTIONS**:
  - Check confidence score of each section
  - If any < 0.85 → FLAG
  - Collect all `uncertain_spans`

  **4. UNDOCUMENTED ENTITIES**:
  - Compare extracted entities in Session Context against SOAP content
  - If extracted symptom absent from Subjective → FLAG
  - If extracted medication absent from Plan → FLAG
  - If extracted lab value absent from Objective → FLAG
  - Exception: `pending_manual_entry` lab values (expected, don't flag)

  **5. PROVENANCE INTEGRITY**:
  - Every entity has provenance record (source, speaker, utterance, verified)?
  - If any missing → FLAG
  - If unverified lab value present without flag → FLAG

- **Overall Confidence**: Weighted average
  - Subjective 25%, Objective 25%, Assessment 25%, Plan 25%

- **Pass Criteria**: `pass = true` ONLY if ALL:
  - All four sections present and non-empty
  - No population mismatch
  - `overall_confidence >= 0.85`
  - No undocumented entities
  - All entities have provenance records

- **Output**:
  ```json
  {
    "overall_confidence": 0.87,
    "section_scores": {
      "subjective": 0.92,
      "objective": 0.85,
      "assessment": 0.88,
      "plan": 0.83
    },
    "flags": [
      {
        "failure_mode": "low_confidence",
        "section": "plan",
        "detail": "Medication dosage uncertain - verify metformin 1000mg"
      }
    ],
    "pass": false
  }
  ```

- **Next**: Node 14 (Clinical Safety Guardrail)

---

### **Phase 9: Safety Validation**

#### Node 14: EVALUATOR/GUARDRAIL — Clinical Safety
- **Type**: Evaluator/Guardrail
- **Model**: Groq + Llama 3.1 70B
- **Function**: Check for patient safety risks
- **Design Principle**: False positives acceptable, false negatives are not

- **Three Safety Checks**:

  **1. DANGEROUS DRUG COMBINATIONS**:
  - Cross-reference medications against known dangerous interactions
  - Examples:
    - Warfarin + Aspirin (bleeding risk)
    - SSRIs + MAOIs (serotonin syndrome)
    - Metformin + Contrast agents (lactic acidosis)
    - ACE inhibitors + Potassium supplements (hyperkalemia)
    - NSAIDs + Anticoagulants (bleeding)
  - If found → FLAG

  **2. RED FLAG DIAGNOSES**:
  - Check Assessment for conditions requiring immediate escalation:
    - Suspected MI or acute coronary syndrome
    - Stroke or TIA indicators
    - Sepsis indicators
    - Acute respiratory failure
    - Hypertensive emergency (BP > 180/120)
    - Diabetic ketoacidosis
  - If found → mark `urgency: URGENT`

  **3. DOSAGE RISK**:
  - Check Plan medications for dosages exceeding safe ranges
  - Flag abnormally high dosages

- **Output**:
  ```json
  {
    "safety_pass": false,
    "safety_flags": [
      {
        "check_type": "drug_interaction",
        "detail": "Warfarin + Aspirin combination detected - bleeding risk",
        "urgency": "review"
      }
    ]
  }
  ```

- **Critical**: `safety_pass: false` if ANY safety flag exists. Does not modify SOAP note — only flags and reports.

- **Next**: Node 15 (Safety Flag Router)

---

### **Phase 10: Routing Logic**

#### Node 15: CONDITION/BRANCH — Safety Flag Router
- **Type**: Condition/Branch
- **Condition**: `safety_pass == false`
- **True Path** (safety flag exists): → Node 17 (Human Handoff Urgent Safety)
- **False Path** (no safety flags): → Node 16 (Confidence Router)

**Critical**: Safety escalation takes absolute priority over confidence routing. Any safety flag routes immediately to urgent handoff regardless of documentation confidence score.

#### Node 16: CONDITION/BRANCH — Confidence Router
- **Type**: Condition/Branch
- **Condition**: `overall_confidence >= 0.85 AND pass == true`
- **True Path**: → Node 19 (Output Formatter)
- **False Path**: → Node 18 (Human Handoff Low Confidence)

**Threshold Rationale**: 0.85 is clinically defensible — high enough for reliability, low enough to avoid unnecessary routing.

**No Retry Loop**: If AI confidence is below threshold, correct response is physician review, not automated regeneration.

**Accuracy vs Speed Trade-off**: 
- Above 0.85: Both satisfied
- Below 0.85: Accuracy wins, speed sacrificed

---

### **Phase 11: Human Handoff**

#### Node 17: HUMAN HANDOFF — Urgent Safety Escalation
- **Type**: Human Handoff
- **Trigger**: Clinical Safety Guardrail detected safety risk
- **Urgency**: URGENT
- **Message**:
  ```
  URGENT — SAFETY FLAG DETECTED
  
  This SOAP note has been flagged by the Clinical Safety
  Guardrail and requires immediate physician review.
  
  Safety flags raised:
  - [Drug interaction: Warfarin + Aspirin - bleeding risk]
  
  The note has NOT been saved.
  Your review and explicit approval are required.
  ```

- **Physician Action**: Review flags, edit note, approve
- **Next**: Node 19 (Output Formatter)

#### Node 18: HUMAN HANDOFF — Low Confidence Review
- **Type**: Human Handoff
- **Trigger**: QA Agent found documentation quality issues
- **Urgency**: Standard review
- **Message**:
  ```
  SOAP NOTE REQUIRES PHYSICIAN REVIEW
  
  This note did not meet the automated quality threshold
  (0.85 confidence) and has been routed for your review.
  
  Overall confidence score: 0.82
  Quality flags raised:
  - [Low confidence: Plan section - medication dosage uncertain]
  - [Unverified lab value: HbA1c mentioned verbally but not in test report]
  
  Uncertain sections are highlighted below.
  The note will NOT be saved until you approve.
  ```

- **Physician Action**: Review flagged sections, input missing values, approve
- **Next**: Node 19 (Output Formatter)

---

### **Phase 12: Final Output**

#### Node 19: OUTPUT FORMATTER
- **Type**: Output Formatter
- **Function**: Format final approved SOAP note for physician dashboard
- **Convergence Point**: All three paths (direct, urgent safety, low confidence) converge here

- **Output Structure**:

  ```markdown
  # SOAP Note — [Date] [Time]
  
  ## QA Summary
  - Subjective: 0.92 🟢
  - Objective: 0.85 🟢
  - Assessment: 0.88 🟢
  - Plan: 0.83 🟡
  
  ---
  
  ## SUBJECTIVE
  Patient reports chest pain for 3 days, worsening when lying down.
  Shortness of breath at night. No radiation to arm or jaw.
  
  ## OBJECTIVE
  - BP: 148/92 mmHg
  - HR: 88 bpm
  - HbA1c: 8.2% (OCR verified)
  - ECG: Normal sinus rhythm
  
  ## ASSESSMENT
  1. Type 2 Diabetes — uncontrolled (ICD-10: E11.65)
  2. Essential Hypertension (ICD-10: I10)
  
  ## PLAN
  1. Increase metformin to 1000mg twice daily. (ADA 2024 §6.5)
  2. Start lisinopril 10mg once daily. (JNC 8 Guidelines)
  3. Follow up in 2 weeks for BP recheck.
  4. Order lipid panel.
  
  ---
  
  ## PROVENANCE PANEL (Collapsible)
  
  ### Subjective Entities
  - **"chest pain for 3 days"**
    - Source: Transcript
    - Speaker: Patient
    - Utterance: "My chest has been hurting for 3 days"
    - Verified: Yes
    - Confidence: 0.95
  
  ### Objective Entities
  - **"HbA1c: 8.2%"**
    - Source: Both (transcript + OCR)
    - Speaker: Doctor (verbal) + OCR System
    - Utterance: "Your HbA1c is 8.2"
    - Verified: Yes (OCR confirmed)
    - Confidence: 0.98
  
  ---
  
  [APPROVE BUTTON]
  This note will not be saved until you approve.
  ```

- **Stamps**:
  - From direct path: "AUTOMATED QA PASSED"
  - From urgent safety: "URGENT SAFETY REVIEW"
  - From low confidence: "PHYSICIAN REVIEWED"

- **Critical**: Note NOT saved until physician clicks Approve. Copilot, not autopilot.

---

## Data Flow Diagram

```
┌─────────────┐
│   Doctor    │
│ Presses     │
│  Record     │
└──────┬──────┘
       │
       ├──────────────────────────────────┐
       │                                   │
       ▼                                   ▼
┌─────────────┐                    ┌─────────────┐
│ Audio       │                    │ Screen      │
│ Capture     │                    │ Capture     │
└──────┬──────┘                    └──────┬──────┘
       │                                   │
       ▼                                   ▼
┌─────────────┐                    ┌─────────────┐
│faster-      │                    │ PaddleOCR   │
│whisper STT  │                    │             │
└──────┬──────┘                    └──────┬──────┘
       │                                   │
       ▼                                   ▼
┌─────────────┐                    ┌─────────────┐
│pyannote     │                    │ OCR         │
│Diarization  │                    │ Fallback    │
└──────┬──────┘                    └──────┬──────┘
       │                                   │
       └───────────┬───────────────────────┘
                   │
                   ▼
            ┌─────────────┐
            │ Merge/Join  │
            └──────┬──────┘
                   │
                   ▼
            ┌─────────────┐
            │ Clinical    │
            │ Relevance   │
            │ Filter      │
            └──────┬──────┘
                   │
                   ▼
            ┌─────────────┐
            │ Clinical    │
            │ Extractor   │
            └──────┬──────┘
                   │
                   ▼
            ┌─────────────┐
            │ Session     │
            │ Context     │
            │ Store       │
            └──────┬──────┘
                   │
       ┌───────────┴───────────┐
       │                       │
       ▼                       ▼
┌─────────────┐         ┌─────────────┐
│ Hybrid RAG  │         │ (stored for │
│ Knowledge   │         │ QA Agent)   │
│ Retrieval   │         └─────────────┘
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ SOAP Note   │
│ Generator   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ ICD-10      │
│ Mapper      │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ QA          │
│ Guardrail   │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Clinical    │
│ Safety      │
│ Guardrail   │
└──────┬──────┘
       │
       ├─────────────────┬─────────────────┐
       │                 │                 │
       ▼                 ▼                 ▼
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Safety Flag │   │ Confidence  │   │ Direct to   │
│ → Urgent    │   │ Router      │   │ Output      │
│ Handoff     │   │ → Low Conf  │   │ Formatter   │
│             │   │ Handoff     │   │             │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       └─────────────────┴─────────────────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ Output      │
                  │ Formatter   │
                  └──────┬──────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ Physician   │
                  │ Approval    │
                  └──────┬──────┘
                         │
                         ▼
                  ┌─────────────┐
                  │ SQLite      │
                  │ Save        │
                  └─────────────┘
```

---

## Project Directory Structure

```
medscribe/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Configuration management
│   ├── database.py                # SQLite connection
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # API endpoints
│   │   └── dependencies.py        # Shared dependencies
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── graph.py               # LangGraph pipeline definition
│   │   ├── state.py               # State schema
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── filter.py          # Clinical Relevance Filter
│   │   │   ├── extractor.py       # Clinical Extractor
│   │   │   ├── rag.py             # Hybrid RAG
│   │   │   ├── soap.py            # SOAP Generator
│   │   │   ├── qa.py              # QA Guardrail
│   │   │   └── safety.py          # Safety Guardrail
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── whisper.py         # faster-whisper integration
│   │       ├── diarization.py     # pyannote-audio integration
│   │       ├── ocr.py             # PaddleOCR integration
│   │       └── icd10.py           # ICD-10 CDC API
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py             # Pydantic data models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py                 # Groq API client
│   │   └── rag.py                 # ChromaDB service
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py              # Logging configuration
│   │   └── validators.py          # Input validation
│   └── requirements.txt
├── frontend/
│   ├── public/
│   │   └── index.html
│   ├── src/
│   │   ├── components/
│   │   │   ├── RecordButton.jsx   # Audio recording UI
│   │   │   ├── SOAPDisplay.jsx    # SOAP note display
│   │   │   ├── ProvenancePanel.jsx # Provenance viewer
│   │   │   └── ApproveButton.jsx  # Approval UI
│   │   ├── services/
│   │   │   └── api.js             # API client
│   │   ├── App.jsx                # Main app component
│   │   └── index.js               # Entry point
│   ├── package.json
│   └── tailwind.config.js
├── data/
│   ├── guidelines/                # Clinical guidelines corpus
│   │   ├── ada_guidelines.pdf
│   │   ├── who_protocols.pdf
│   │   └── icd10_reference.json
│   ├── chromadb/                  # ChromaDB vector store
│   └── medscribe.db               # SQLite database
├── docs/
│   ├── ARCHITECTURE.md            # This file
│   ├── API.md                     # API documentation
│   ├── SETUP.md                   # Setup instructions
│   └── WORKFLOW.md                # Detailed workflow explanation
├── tests/
│   ├── backend/
│   │   ├── test_pipeline.py
│   │   ├── test_agents.py
│   │   └── test_tools.py
│   └── frontend/
│       └── test_components.js
├── .env.example                   # Environment variables template
├── .gitignore
├── README.md                      # Project overview
└── docker-compose.yml             # Optional containerization
```

---

## API Endpoints

### POST /api/consultation
**Description**: Start a new consultation session

**Request**:
```json
{
  "audio_file": "<base64_encoded_audio>",
  "screen_capture": "<base64_encoded_image>",
  "physician_id": "string"
}
```

**Response**:
```json
{
  "session_id": "uuid",
  "status": "processing",
  "message": "Consultation processing started"
}
```

### GET /api/consultation/{session_id}
**Description**: Get consultation processing status

**Response**:
```json
{
  "session_id": "uuid",
  "status": "completed|processing|failed",
  "soap_note": {...},
  "confidence_scores": {...},
  "flags": [...],
  "requires_review": true|false
}
```

### POST /api/consultation/{session_id}/approve
**Description**: Approve and save SOAP note

**Request**:
```json
{
  "approved": true,
  "edits": {...}
}
```

**Response**:
```json
{
  "saved": true,
  "note_id": "uuid",
  "message": "SOAP note saved successfully"
}
```

### GET /api/guidelines/search
**Description**: Search clinical guidelines (for testing RAG)

**Query Parameters**:
- `query`: Search query
- `population`: adult|pediatric
- `condition`: diabetes|hypertension|etc

**Response**:
```json
{
  "results": [
    {
      "content": "...",
      "source": "ADA 2024 §6.5",
      "relevance_score": 0.89
    }
  ]
}
```

---

## Key Design Decisions

### 1. **Why Local-First Architecture?**
- **Cost**: Rs. 0/month for compute (all processing local)
- **Privacy**: Patient data never leaves the physician's machine
- **Latency**: No network round-trips for STT, OCR, or RAG
- **Reliability**: Works offline (except Groq API calls)

### 2. **Why Groq + Llama 3.1 70B?**
- **Free tier**: Generous limits for single-physician use
- **Speed**: Groq's LPU inference is extremely fast
- **Medical reasoning**: Llama 3.1 70B has strong medical knowledge
- **Open source**: Can switch to local Llama if needed

### 3. **Why faster-whisper over OpenAI Whisper API?**
- **Cost**: Free vs. $0.006/minute
- **Privacy**: Audio never leaves local machine
- **Speed**: GPU-accelerated, real-time capable
- **Reliability**: No API rate limits or downtime

### 4. **Why pyannote-audio for Diarization?**
- **Accuracy**: State-of-the-art speaker diarization
- **Free**: HuggingFace model, no API costs
- **Integration**: Works seamlessly with faster-whisper output

### 5. **Why PaddleOCR over Google Cloud Vision?**
- **Cost**: Free vs. $1.50/1000 images
- **Privacy**: Images never leave local machine
- **Medical documents**: Handles printed lab reports well
- **Speed**: Fast inference on CPU/GPU

### 6. **Why ChromaDB for RAG?**
- **Local**: No external vector database service
- **Free**: Open source, no licensing costs
- **Simple**: Easy setup, minimal configuration
- **Sufficient**: Handles guideline corpus size well

### 7. **Why SQLite for SOAP Storage?**
- **Simplicity**: Single file, no server setup
- **Sufficient**: Single-physician use case
- **Portable**: Easy backup and migration
- **Free**: No database licensing

### 8. **Why No Automated Retry Loop?**
- **Clinical safety**: Uncertain outputs must surface to physician
- **False confidence**: Regeneration doesn't improve accuracy, just confidence score
- **Transparency**: Physician sees actual AI uncertainty

### 9. **Why Two Separate Guardrails (QA + Safety)?**
- **Defense in depth**: Documentation quality ≠ patient safety
- **Different urgency**: Safety flags require immediate attention
- **Clear separation**: QA checks completeness, Safety checks harm

### 10. **Why Copilot Not Autopilot?**
- **Legal liability**: Physician must review and approve
- **Clinical responsibility**: Doctor is accountable, not AI
- **Trust building**: Transparency builds physician confidence
- **Error correction**: Physician catches AI mistakes

---

## Success Criteria (Phase 1)

### Functional Requirements
- ✅ POST /consultation endpoint accepts audio file
- ✅ faster-whisper transcribes audio with diarization
- ✅ Clinical Relevance Filter explains inclusion/exclusion
- ✅ Clinical Extractor extracts entities with provenance
- ✅ SOAP Generator produces structured note
- ✅ Pydantic response model validates output

### Quality Requirements
- ✅ Speaker attribution integrity (confidence threshold)
- ✅ Lab value cross-verification (verbal vs OCR)
- ✅ No hallucination (explicit unavailable signals)
- ✅ Provenance tracking (source, speaker, utterance)
- ✅ Confidence scoring (per-section, overall)

### Performance Requirements
- ✅ < 30 seconds AI processing time
- ✅ < 20 seconds physician review time
- ✅ 2+ hours daily time savings per physician

### Cost Requirements
- ✅ Rs. 0/month compute (all local)
- ✅ Groq API within free tier limits
- ✅ No cloud service costs

---

## Next Steps

1. **Review this architecture plan** — Confirm alignment with your vision
2. **Switch to Code mode** — Begin implementation
3. **Phase 1 implementation order**:
   - Set up project structure
   - Implement FastAPI backend foundation
   - Integrate faster-whisper + pyannote-audio
   - Build Clinical Relevance Filter (Agent 1)
   - Build Clinical Extractor (Agent 2)
   - Implement basic SOAP Generator
   - Create Pydantic schemas
   - Test end-to-end flow

4. **Future phases** (not in Phase 1):
   - PaddleOCR integration
   - Hybrid RAG with ChromaDB
   - QA and Safety Guardrails
   - Human Handoff mechanisms
   - Frontend React app
   - Full 19-node pipeline

---

