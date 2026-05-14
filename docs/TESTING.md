# MedScribe Testing Guide

This guide explains how to test the MedScribe Phase 1 MVP implementation.

## Overview

Phase 1 includes three testing scripts:

1. **`tests/test_phase1.py`** - Unit tests for all components (no audio required)
2. **`tests/generate_test_audio.py`** - Generates synthetic test audio
3. **`tests/test_api.py`** - End-to-end API test with audio file

## Prerequisites

### Required Dependencies

Install all backend dependencies:

```bash
pip install -r backend/requirements.txt
```

### Configuration

Create `.env` file with required API keys:

```bash
cp .env.example .env
```

Edit `.env` and set:

```
GROQ_API_KEY=your_actual_groq_api_key_here
HF_TOKEN=your_actual_huggingface_token_here
```

**Getting API Keys:**

1. **Groq API Key** (Free):
   - Sign up at https://console.groq.com
   - Navigate to API Keys section
   - Create new API key
   - Copy and paste into `.env`

2. **HuggingFace Token** (Free):
   - Sign up at https://huggingface.co
   - Go to Settings → Access Tokens
   - Create new token with read permissions
   - Copy and paste into `.env`
   - **IMPORTANT**: Accept terms at https://huggingface.co/pyannote/speaker-diarization-3.1

## Testing Steps

### Step 1: Component Tests (No Audio Required)

Run the component test suite:

```bash
python tests/test_phase1.py
```

**What it tests:**

1. ✅ Configuration loading (`.env` file)
2. ✅ LLM service (Groq API connection)
3. ✅ Whisper model loading
4. ✅ Pyannote diarization model loading
5. ✅ Clinical Relevance Filter (with mock data)
6. ✅ Clinical Extractor (with mock data)
7. ✅ SOAP Generator (with mock data)
8. ✅ Complete pipeline structure

**Expected output:**

```
TEST SUMMARY
================================================================================
✅ PASS - Configuration
✅ PASS - LLM Service
✅ PASS - Whisper Transcription
✅ PASS - Pyannote Diarization
✅ PASS - Clinical Relevance Filter
✅ PASS - Clinical Extractor
✅ PASS - SOAP Generator
✅ PASS - Complete Pipeline

Total: 8/8 tests passed

🎉 ALL TESTS PASSED! Phase 1 is ready for audio testing.
```

**Common Issues:**

- **"GROQ_API_KEY not configured"**: Edit `.env` file with actual API key
- **"HuggingFace token error"**: Accept terms at pyannote model page
- **"Import error"**: Run `pip install -r backend/requirements.txt`

### Step 2: Generate Test Audio (Optional)

If you don't have a test audio file, generate one:

```bash
python tests/generate_test_audio.py
```

**Requirements:**

Install TTS dependencies (choose one):

```bash
# Option 1: Offline TTS (recommended)
pip install pyttsx3 pydub

# Option 2: Online TTS (requires internet)
pip install gtts pydub
```

**What it does:**

- Creates `tests/test_consultation.wav`
- Simulates doctor-patient consultation
- ~16 utterances, ~60 seconds duration
- Includes symptoms, vitals, medications

**Alternative:**

Record your own audio file:
- Format: WAV
- Sample rate: 16kHz recommended
- Duration: 30-120 seconds
- Content: Doctor-patient consultation

### Step 3: Start the Server

In one terminal, start the FastAPI server:

```bash
python backend/main.py
```

**Expected output:**

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Server endpoints:**

- `GET /health` - Health check
- `GET /` - API info
- `POST /api/consultation` - Process consultation audio

### Step 4: Test the API

In another terminal, run the API test:

```bash
python tests/test_api.py
```

**What it does:**

1. Checks if server is running
2. Uploads test audio file
3. Waits for processing (30-60 seconds first run)
4. Displays SOAP note result
5. Runs quality checks
6. Saves full response to `tests/test_result.json`

**Expected output:**

```
MEDSCRIBE API TEST
================================================================================
Test audio: tests/test_consultation.wav
API endpoint: http://localhost:8000/api/consultation
Audio size: 245.3 KB
✅ Server is running

Sending consultation request...
(This may take 30-60 seconds for first run while models load)

✅ Request successful!
Processing time: 45.2 seconds

SOAP NOTE RESULT
================================================================================

[SUBJECTIVE]
Confidence: 0.88
Patient reports chest pain for 3 days, worsening when lying down...

[OBJECTIVE]
Confidence: 0.92
Blood pressure: 148/92 mmHg (elevated)...

[ASSESSMENT]
Confidence: 0.85
1. Hypertension - uncontrolled
2. Chest pain - likely cardiac origin...

[PLAN]
Confidence: 0.90
1. Increase metformin to 1000mg twice daily
2. Prescribe amlodipine 5mg once daily...

QUALITY CHECKS
================================================================================
✅ All SOAP sections present
✅ Average confidence >= 0.70
✅ Entity provenance present
✅ Processing time < 120s

Quality Score: 4/4 checks passed

Full response saved to: tests/test_result.json

🎉 ALL CHECKS PASSED!
```

### Step 5: Manual API Testing (Optional)

Test with curl:

```bash
curl -X POST http://localhost:8000/api/consultation \
  -F "audio_file=@tests/test_consultation.wav"
```

Or use Postman/Insomnia:
- Method: POST
- URL: `http://localhost:8000/api/consultation`
- Body: form-data
- Key: `audio_file` (type: file)
- Value: Select your audio file

## Quality Criteria

Phase 1 MVP must meet these criteria:

### 1. Functional Requirements

- ✅ Audio transcription works (Whisper)
- ✅ Speaker diarization works (Pyannote)
- ✅ Clinical filtering identifies relevant utterances
- ✅ Entity extraction captures symptoms, medications, vitals
- ✅ SOAP note generation produces all 4 sections
- ✅ API endpoint accepts audio and returns JSON

### 2. Quality Requirements

- ✅ All SOAP sections present (S, O, A, P)
- ✅ Average confidence >= 0.70
- ✅ Entity-level provenance included
- ✅ Processing time < 120 seconds
- ✅ No crashes or errors

### 3. Provenance Requirements

Every clinical entity must include:
- `source`: transcript/ocr/both
- `speaker`: Patient/Doctor
- `utterance`: exact original text
- `verified`: true/false
- `confidence`: 0-1 score

Check in `tests/test_result.json`:

```json
{
  "soap_note": {
    "subjective": {
      "entities": [
        {
          "claim": "chest pain for 3 days",
          "source": "transcript",
          "speaker": "Patient",
          "utterance": "My chest has been hurting for three days",
          "verified": true,
          "confidence": 0.95
        }
      ]
    }
  }
}
```

## Troubleshooting

### Models Taking Too Long to Load

**First run**: Models download and load (30-60 seconds)
**Subsequent runs**: Models cached, faster (10-20 seconds)

**Solution**: Be patient on first run. Models are cached after.

### Out of Memory Errors

**Symptom**: Process killed, "Killed" message

**Solutions**:
1. Use smaller Whisper model in `.env`:
   ```
   WHISPER_MODEL=tiny  # or base, small
   ```
2. Close other applications
3. Increase system swap space

### Diarization Errors

**Symptom**: "HuggingFace token error"

**Solution**:
1. Set `HF_TOKEN` in `.env`
2. Accept terms: https://huggingface.co/pyannote/speaker-diarization-3.1
3. Wait 5 minutes for access to propagate

### Low Confidence Scores

**Symptom**: Confidence < 0.70

**Possible causes**:
1. Poor audio quality
2. Background noise
3. Unclear speech
4. Non-clinical conversation

**Solutions**:
1. Use clearer audio
2. Ensure clinical content in conversation
3. Check transcription accuracy first

### Empty SOAP Sections

**Symptom**: One or more sections empty

**Possible causes**:
1. No relevant content in audio
2. Filter too aggressive
3. LLM parsing error

**Debug steps**:
1. Check `filtered_transcript` in response
2. Check `extracted_entities` in response
3. Review LLM prompts in code

## Next Steps

After Phase 1 tests pass:

1. **Phase 2**: RAG, Guardrails, Routing
   - Hybrid RAG guideline retrieval
   - QA Guardrail (5 failure modes)
   - Clinical Safety Guardrail
   - Confidence routing (0.85 threshold)

2. **Phase 3**: OCR Integration
   - PaddleOCR for test reports
   - Screen capture
   - Lab value cross-verification

3. **Phase 4**: Database & Persistence
   - SQLite schema
   - SOAP note storage
   - Session management

4. **Phase 5**: Human Handoff
   - Urgent safety escalation
   - Low confidence review
   - Physician approval flow

5. **Phase 6**: Frontend
   - React + Tailwind UI
   - Record button
   - SOAP display
   - Provenance panel

## Support

If tests fail:

1. Check error messages carefully
2. Review configuration (`.env`)
3. Verify API keys are valid
4. Check internet connection (for Groq API)
5. Review logs in terminal

For persistent issues, check:
- Python version (3.10+ required)
- Disk space (models need ~2GB)
- RAM (8GB+ recommended)
- Internet connection (for API calls)