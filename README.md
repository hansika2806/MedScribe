# MedScribe — Clinical Documentation AI

## What is MedScribe?
MedScribe captures doctor-patient consultation audio, automatically extracts clinical information, retrieves evidence-based guidelines, and generates a structured SOAP note for physician review and approval. The physician reviews and approves before anything is saved — copilot, not autopilot.

## Key Features
- Real-time audio transcription with faster-whisper
- Speaker diarization — Doctor vs Patient with pyannote-audio
- Clinical relevance filtering with explicit reasoning
- Entity extraction with full provenance tracking
- Population-aware RAG from real guidelines: ADA, WHO, ICMR, PubMed
- ICD-10 code mapping with the NLM CDC API
- PDF lab report OCR with PaddleOCR
- QA guardrail covering 5 failure modes
- Clinical safety guardrail for drug interactions, red flag diagnoses, and dosage risks
- Intelligent routing: urgent review, low-confidence review, or standard approval
- Physician approval required before saving
- SQLite persistence with full provenance

## Technology Stack

| Component | Technology | Cost |
|---|---|---|
| Backend API | FastAPI | Free |
| Pipeline | LangGraph | Free |
| LLM | Groq API + Llama 3.3 70B | Free tier |
| Speech-to-text | faster-whisper | Free, local |
| Speaker diarization | pyannote-audio | Free with HuggingFace token |
| OCR | PaddleOCR | Free, local |
| RAG database | ChromaDB | Free, local |
| Persistence | SQLite | Free, local |
| Frontend | React + Tailwind CSS | Free |

Total: Rs. 0/month for local prototype/demo usage, subject to free-tier API limits.

## Demo Credentials

| Username | Password | Name | Department |
|---|---|---|---|
| dr.sharma | medscribe123 | Dr. Priya Sharma | General Medicine |
| dr.kumar | medscribe123 | Dr. Rahul Kumar | Cardiology |
| dr.patel | medscribe123 | Dr. Anjali Patel | Endocrinology |

## Requirements
- Python 3.11+
- Node.js 18+
- FFmpeg (installed via WinGet on Windows)
- 8GB RAM minimum for local AI models
- Internet connection for Groq API and HuggingFace model access

## Setup Instructions

### 1. Get API Keys (free)

Groq API Key:
1. Go to `console.groq.com`
2. Sign up for a free account
3. Open API Keys and create a key
4. Copy the key

HuggingFace Token:
1. Go to `huggingface.co`
2. Sign up for a free account
3. Open Settings, then Access Tokens, then New Token
4. Copy the token
5. Accept model terms at:
   - `huggingface.co/pyannote/speaker-diarization-3.1`
   - `huggingface.co/pyannote/segmentation-3.0`

### 2. Install FFmpeg (Windows)

```powershell
winget install ffmpeg
```

### 3. Clone and Setup

```powershell
git clone <repo>
cd MedScribe

python -m venv venv
venv\Scripts\activate
pip install -r backend/requirements.txt

cd frontend
npm install
cd ..
```

### 4. Configure Environment

```powershell
copy .env.example .env
```

Edit `.env`:

```text
GROQ_API_KEY=your_key_here
HF_TOKEN=your_token_here
LLM_MODEL=llama-3.3-70b-versatile
```

### 5. Run the Application

Terminal 1 — Backend:

```powershell
cd MedScribe
venv\Scripts\activate
python -m backend.main
```

Terminal 2 — Frontend:

```powershell
cd MedScribe/frontend
npm run dev
```

Open: `http://localhost:5173`

Login with the demo credentials above.

## Testing

```powershell
python tests/generate_test_audio.py
python tests/generate_test_pdfs.py
python tests/test_api.py
python tests/test_phase5.py
python tests/test_phase6_diarization.py
python tests/test_final.py
```

## Known Limitations
- Speaker diarization accuracy depends on audio quality and voice distinction.
- Groq free tier has token limits; use `llama-3.1-8b-instant` for heavy testing if needed.
- SQLite is suitable for prototype/demo scale, not multi-tenant production scale.
- Physician accounts are hardcoded for the demo.

## Troubleshooting
See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for common issues.
