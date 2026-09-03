## MedScribe v1.0.0 — Architecture Reference

### 19-Node Pipeline

```text
INPUT
  ↓ (parallel)
WHISPER STT + PYANNOTE DIARIZATION
  ↓
CLINICAL RELEVANCE FILTER (Groq LLM)
  ↓
CLINICAL EXTRACTOR (Groq LLM)
  ↓
SESSION CONTEXT STORE (LangGraph state)
  ↓
HYBRID RAG (ChromaDB + BM25 + Metadata)
  ↓
SOAP GENERATOR (Groq LLM)
  ↓
ICD-10 MAPPER (NLM CDC API)
  ↓
QA GUARDRAIL (Groq LLM — 5 checks)
  ↓
SAFETY GUARDRAIL (Groq LLM — 3 checks)
  ↓
SAFETY ROUTER
  ├─ safety_pass=false → URGENT HANDOFF
  └─ safety_pass=true → CONFIDENCE ROUTER
      ├─ confidence>=0.85 → OUTPUT FORMATTER
      └─ confidence<0.85 → REVIEW HANDOFF
```

### API Endpoints

```text
POST   /auth/login
GET    /auth/me
POST   /consultation
GET    /consultation/{id}
GET    /consultation/{id}/status
POST   /consultation/{id}/labs
POST   /consultation/{id}/approve
POST   /consultation/{id}/retry
GET    /metrics
GET    /performance/{id}
GET    /health
```

### Demo Credentials

```text
dr.sharma / medscribe123 — General Medicine
dr.kumar / medscribe123 — Cardiology
dr.patel / medscribe123 — Endocrinology
```

### Run Commands

```text
Backend:  python -m backend.main
Frontend: cd frontend && npm run dev
Tests:    python tests/test_final.py
URL:      http://localhost:5173
```
