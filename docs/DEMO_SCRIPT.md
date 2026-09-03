# MedScribe Demo Script

## Before You Start
1. Start backend: `python -m backend.main`
   Wait for `All models pre-loaded. Ready.`
2. Start frontend: `npm run dev`
3. Open: `http://localhost:5173`
4. Have test files ready:
   - `tests/test_consultation.wav`
   - `tests/pdfs/sample_lab_report.pdf`

## Demo Flow (5 minutes)

### Step 1 — Login (30 seconds)
- Show login screen.
- Enter: `dr.sharma / medscribe123`.
- Point out: "Physician authentication required."

### Step 2 — Upload (30 seconds)
- Drag and drop `test_consultation.wav`.
- Upload `sample_lab_report.pdf`.
- Show file info and estimated time.
- Click "Start Consultation".
- Point out: "One button — audio and PDF captured simultaneously."

### Step 3 — Processing Screen (60-90 seconds)
- Show pipeline stages progressing.
- Point out: "11-stage AI pipeline running."
- Mention stages: transcribing, diarizing, filtering, extracting, retrieving guidelines, generating SOAP.

### Step 4 — SOAP Review (90 seconds)
- Show the review type banner.
- Point out diarization badge: green means pyannote real diarization.
- Show Subjective: "Extracted from patient speech."
- Show Objective: "Lab values from PDF — HbA1c 8.2%."
- Show Assessment: "ICD-10 codes automatically mapped."
- Show Plan: "Guideline citations from ADA, WHO, ICMR."
- Expand one provenance panel: "Every claim is traceable to its source."
- Show confidence scores per section.

### Step 5 — Safety and QA (30 seconds)
- If `review_type = urgent_safety`, show red safety flags.
- Say: "Drug interaction detected automatically."
- Show QA panel: "5 quality checks verified."

### Step 6 — Approve (30 seconds)
- Click Approve and Save Note.
- Show success screen.
- Point out: "Nothing saved without physician approval — copilot, not autopilot."

### Step 7 — Key Points to Mention
- "100% free technology stack — Rs. 0/month."
- "Local AI components reduce patient data exposure."
- "Saves 2+ hours daily per physician."
- "Real clinical guidelines: ADA 2024, WHO, ICMR."
- "Physician always in the loop."

## Talking Points for Questions

Q: "Is this production ready?"

A: "This is a working prototype demonstrating the full pipeline. Production deployment would add cloud infrastructure, compliance review, and a real physician database."

Q: "How does it handle different languages?"

A: "Currently English only. Whisper supports multilingual transcription, so Hindi and regional language support can be added."

Q: "What about patient privacy?"

A: "faster-whisper and PaddleOCR run locally. Only Groq LLM calls go to the cloud, and the pipeline is designed to avoid sending patient identifiers."

Q: "What happens if AI makes a mistake?"

A: "Physician approval is mandatory before saving. QA guardrails flag low-confidence sections. Safety guardrails catch dangerous drug interactions. Nothing is saved without explicit physician sign-off."
