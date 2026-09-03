# MedScribe - Complete Development Journey

## Table of Contents
1. Project Overview
2. Architecture Decisions
3. Technology Stack - Why Each Tool Was Chosen
4. Phase 1 - Core Pipeline
5. Phase 2 - RAG and Guardrails
6. Phase 3 - Frontend and Storage
7. Phase 4 - OCR Integration
8. Phase 5 - Authentication and Polish
9. Known Issues and Current Status
10. Commands Reference

---

## SECTION 1: PROJECT OVERVIEW

MedScribe is a clinical documentation AI for physicians. It takes consultation audio, optionally combines it with uploaded lab-report PDFs, and produces a structured SOAP note with confidence scores, source provenance, guideline citations, QA checks, and clinical safety checks.

It was built for doctors who lose time after every consultation turning spoken encounters into structured documentation. The key product principle is copilot, not autopilot: the system drafts, cites, flags uncertainty, and requires physician approval before a note is considered saved.

The claimed time saving is based on reducing manual documentation from roughly 14-19 minutes per consultation to a review workflow. Across a typical daily clinic load, that can recover about 2.3-3.2 hours per day, or roughly 23-32 full working days per year.

---

## SECTION 2: ARCHITECTURE DECISIONS

### DECISION 1: LLM Provider - Groq + Llama 3.3 70B
Decision: use Groq with Llama 3.3 70B for clinical reasoning steps.

Why: Groq has fast inference and a usable free tier around 100k tokens per day. OpenAI was rejected for this prototype because it costs money and does not provide the same free local-demo economics. Ollama was rejected because a high-quality 70B local workflow requires a powerful GPU.

Failure discovered: heavy testing hit the Groq 429 daily limit. Workaround: use `llama-3.1-8b-instant` for testing and switch back to `llama-3.3-70b-versatile` for demos.

### DECISION 2: Speech-to-Text - faster-whisper local
Decision: use local `faster-whisper`.

Why: it is free, private, runs locally, and provides Whisper-grade transcription. OpenAI Whisper API was rejected because it costs money per minute. Limitation: CPU transcription is slower than an API, often 15-20 seconds for 90 seconds of audio.

### DECISION 3: Speaker Diarization - pyannote then Speechbrain
Original plan: `pyannote/speaker-diarization-3.1`.

Problems: `use_auth_token` deprecation, internal pyannote/huggingface version mismatches, model access requirements, and Hub connection failures. Downgrading `huggingface_hub` created other incompatibilities.

Resolution: switch to Speechbrain `spkrec-ecapa-voxceleb`. Speechbrain then hit Windows `WinError 1314` because symlink creation requires privileges. Phase 5 sets local Speechbrain storage and disables symlink warnings. If Speechbrain still fails, fallback alternating Doctor/Patient diarization continues and logs the selected method.

### DECISION 4: OCR - PaddleOCR with PyMuPDF
Decision: upload full PDFs, convert pages with PyMuPDF, and OCR with PaddleOCR.

Why: Google Cloud Vision requires billing, Tesseract has lower medical-report accuracy, and PaddleOCR is free/local. PDF upload was chosen over screen capture because screen capture only sees the visible portion while reports can span multiple pages.

### DECISION 5: RAG Database - ChromaDB local
Decision: use ChromaDB for local vector retrieval.

Why: it is free, local, and pip-installable. Pinecone requires an account and cost planning. FAISS was rejected because it adds setup complexity for the same prototype outcome. Corpus: 8 real guidelines plus 24 PubMed abstracts, 32 documents total.

### DECISION 6: Vector Embeddings - sentence-transformers
Decision: use `all-MiniLM-L6-v2`.

Why: free, local, fast, and good enough for semantic guideline retrieval. OpenAI embeddings were rejected because they add cost.

### DECISION 7: Pipeline Orchestration - LangGraph
Decision: use LangGraph to pass state between pipeline nodes.

Why: the workflow has many dependent steps, conditional routes, and error states. Plain functions were rejected because manual state passing and conditional edges became harder to reason about.

### DECISION 8: Database - SQLite
Decision: use SQLite.

Why: zero setup, single file, sufficient for prototype and demo scale. PostgreSQL is the Phase 6 migration path when concurrent multi-user deployment matters.

### DECISION 9: Frontend - React + Vite + Tailwind
Decision: React for components, Vite for fast dev, Tailwind for styling.

Why: the review UI is component-heavy and benefits from reusable panels. Next.js was rejected as unnecessary infrastructure for a local prototype.

### DECISION 10: Authentication - JWT with hardcoded users
Decision: stateless JWT auth with three physician accounts.

Why: enough for Phase 5 demo security and identity threading. A real physician database is explicitly deferred to Phase 6.

---

## SECTION 3: TECHNOLOGY STACK

| Component | Technology | Version | Cost | Why |
|---|---|---|---|---|
| LLM | Groq + Llama 3.3 70B | latest | Free 100k/day | Fast, free |
| Speech-to-Text | faster-whisper | 1.0.3 | Free | Local, accurate |
| Diarization | Speechbrain + fallback alternating | 0.5.16 | Free | Real attempt plus robust fallback |
| OCR | PaddleOCR | 2.8.1 | Free | Local, accurate |
| PDF Processing | PyMuPDF | 1.23.8 | Free | PDF to image conversion |
| RAG | ChromaDB + sentence-transformers | 0.4.22 | Free | Local vector store |
| BM25 | rank-bm25 | 0.2.2 | Free | Keyword scoring |
| Pipeline | LangGraph | 0.0.20 | Free | State management |
| Backend | FastAPI | 0.104.1 | Free | Modern Python API |
| Auth | python-jose + passlib | 3.3.0 / 1.7.4 | Free | JWT tokens |
| Database | SQLite | built-in | Free | Zero setup |
| Frontend | React + Vite | 18 + 5 | Free | Component UI |
| Styling | Tailwind CSS | 3.4 | Free | Utility CSS |
| Audio | ffmpeg | 8.1.1 | Free | Audio processing |
| Guidelines | PubMed Entrez API | - | Free | Real abstracts |
| ICD-10 | NLM Clinical Tables API | - | Free | Current codes |

Total monthly cost: Rs. 0 for the prototype.

---

## SECTION 4: PHASE 1 - CORE PIPELINE

### What was built
FastAPI backend foundation, faster-whisper transcription, fallback speaker diarization, Clinical Relevance Filter, Clinical Extractor, SOAP Generator, and the first LangGraph pipeline.

### Pipeline flow diagram
```
INPUT (audio file)
      |
TRANSCRIBE (faster-whisper)
      |
DIARIZE (Speechbrain or fallback)
      |
CLINICAL RELEVANCE FILTER
      |
CLINICAL EXTRACTOR
      |
SOAP GENERATOR
      |
OUTPUT
```

### Problems encountered and fixes
Requirements were initially empty, causing missing modules. Running `python main.py` caused import-path errors, fixed by `python -m backend.main`. Pyannote failed through multiple HuggingFace auth/version paths, leading to Speechbrain and fallback diarization. A decommissioned Groq model was replaced with `llama-3.3-70b-versatile`. LLM JSON caused Pydantic validation failures, fixed by sanitization and optional/default schema fields. The clinical filter was too strict with fallback diarization, fixed by pass-through when too few utterances survive. Groq 429 limits were handled by switching to the smaller testing model.

---

## SECTION 5: PHASE 2 - RAG AND GUARDRAILS

### What was built
ChromaDB vector database, PubMed Entrez fetch, hybrid scoring, ICD-10 NLM integration, QA guardrail, safety guardrail, review routing, and metrics.

### RAG architecture diagram
```
EXTRACTED ENTITIES
      |
POPULATION TAG FILTER
      |
HYBRID SCORING = cosine + BM25 + metadata
      |
TOP GUIDELINES WITH CITATIONS
```

### Routing logic diagram
```
QA GUARDRAIL
      |
SAFETY GUARDRAIL
      |
SAFETY FAILED -> URGENT HANDOFF
SAFETY PASSED -> confidence >= 0.85 ? STANDARD : LOW CONFIDENCE REVIEW
```

Guideline corpus: ADA 2024, JNC 8, WHO diabetes, AHA/ACC 2021, ICMR 2023, ADA Pediatric 2024, AAP 2017, and PubMed abstracts.

Problems: ChromaDB telemetry warning was non-breaking. Speechbrain Windows symlink failure required fallback diarization and later Phase 5 local-storage fixes.

---

## SECTION 6: PHASE 3 - FRONTEND AND STORAGE

### What was built
React/Vite/Tailwind frontend, SQLite persistence, review workflow, status polling, error screen, safety and QA panels, provenance panels, guideline citations, lab-value input, and approval persistence.

### Frontend component tree
```
App.jsx
  LoginScreen.jsx
  NavBar.jsx
  UploadScreen.jsx
  ProcessingScreen.jsx
  ErrorScreen.jsx
  SOAPReview.jsx
    SafetyFlagsPanel.jsx
    QAFlagsPanel.jsx
    SOAPSection.jsx
      ProvenancePanel.jsx
      GuidelineCitations.jsx
    LabValueInput.jsx
    ApproveButton.jsx
  ApprovalSuccessScreen.jsx
```

### SQLite database schema
`consultations`, `soap_notes`, `diagnoses`, `provenance_records`, `retrieved_guidelines`, `qa_results`, `safety_results`, `lab_values`, and Phase 5 `approvals`.

### State machine diagram
```
login -> upload -> processing -> review -> success
                         \-> error -> upload
```

Problems: CORS origin mismatch was fixed by allowing both localhost forms. Route prefix mismatch was fixed by standardizing frontend calls to the unprefixed API routes.

---

## SECTION 7: PHASE 4 - OCR INTEGRATION

### What was built
PaddleOCR PDF processing, PyMuPDF page conversion, lab regex extraction, optional PDF upload, OCR values in Objective, specialty samples, performance logging, and `/performance/{session_id}`.

### OCR pipeline diagram
```
PDF upload
  -> PyMuPDF page images at 300 DPI
  -> PaddleOCR text lines
  -> lab regex extraction
  -> pipeline state
  -> SOAP Objective with OCR provenance
```

Performance logs are stored in `data/performance_logs.jsonl` with timestamp, session id, node, status, duration, input/output sizes, and metadata.

---

## SECTION 8: PHASE 5 - AUTHENTICATION AND POLISH

### What was built
JWT auth with `python-jose`, password verification with `passlib[bcrypt]`, three demo physician accounts, login screen, protected consultation/approval/metrics endpoints, identity-aware persistence, NavBar, better errors, processing progress bar, approval success screen, mobile responsive improvements, empty states, ffmpeg auto-PATH, and Speechbrain local-storage setup.

### Auth flow diagram
```
Open app
  -> LoginScreen
  -> POST /auth/login
  -> JWT token valid for 8 hours
  -> sessionStorage token + physician
  -> API Authorization: Bearer token
  -> 401 redirects to login
```

### Demo accounts
| Username | Password | Name | Department |
|---|---|---|---|
| dr.sharma | medscribe123 | Dr. Priya Sharma | General Medicine |
| dr.kumar | medscribe123 | Dr. Rahul Kumar | Cardiology |
| dr.patel | medscribe123 | Dr. Anjali Patel | Endocrinology |

---

## SECTION 9: KNOWN ISSUES AND CURRENT STATUS

Working correctly: transcription, extraction, SOAP generation, RAG, ICD-10 lookup, QA guardrails, safety guardrails, routing, React review UI, SQLite persistence, PDF OCR, JWT authentication, and performance logging.

Known limitations: diarization may fall back to alternating speakers on Windows, Groq free tier can be exhausted, no real physician database yet, and ChromaDB telemetry can log non-breaking warnings.

---

## SECTION 10: COMPLETE COMMANDS REFERENCE

### Initial setup
```bat
cd C:\Users\nagah\Projects\MedScribe
python -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
cd frontend
npm install
cd ..
copy .env.example .env
```

Set `GROQ_API_KEY` and optionally `HF_TOKEN` in `.env`.

### Running
```bat
cd C:\Users\nagah\Projects\MedScribe
venv\Scripts\activate
python -m backend.main
```

```bat
cd C:\Users\nagah\Projects\MedScribe\frontend
npm run dev
```

Open `http://localhost:5173` and log in with `dr.sharma / medscribe123`.

### Testing
```bat
python tests\test_api.py
python tests\test_phase4.py
python tests\test_phase5.py
```

### Troubleshooting
Use `docs/TROUBLESHOOTING.md` for exact errors, root causes, fixes, and prevention notes.
