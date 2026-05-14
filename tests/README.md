# MedScribe Testing Suite

This directory contains all testing scripts for MedScribe Phase 1 MVP.

## Test Files

### 1. `test_phase1.py` - Component Unit Tests

Tests all components without requiring audio files.

**Run:**
```bash
python tests/test_phase1.py
```

**Tests:**
- Configuration loading
- LLM service (Groq API)
- Whisper model loading
- Pyannote diarization model loading
- Clinical Relevance Filter (with mock data)
- Clinical Extractor (with mock data)
- SOAP Generator (with mock data)
- Complete pipeline structure

**Duration:** ~30-60 seconds (first run), ~10-20 seconds (cached)

### 2. `generate_test_audio.py` - Test Audio Generator

Generates synthetic doctor-patient consultation audio.

**Run:**
```bash
python tests/generate_test_audio.py
```

**Requirements:**
```bash
pip install pyttsx3 pydub  # Offline TTS
# OR
pip install gtts pydub     # Online TTS
```

**Output:** `tests/test_consultation.wav`

### 3. `test_api.py` - End-to-End API Test

Tests the complete API endpoint with audio file.

**Run:**
```bash
# First, start the server in another terminal:
python backend/main.py

# Then run the test:
python tests/test_api.py
```

**Requirements:**
- Server must be running
- Test audio file must exist (`test_consultation.wav`)

**Output:** `tests/test_result.json` (full API response)

## Quick Start

### Minimal Testing (No Audio)

```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Configure .env
cp .env.example .env
# Edit .env with your API keys

# 3. Run component tests
python tests/test_phase1.py
```

### Full Testing (With Audio)

```bash
# 1. Generate test audio
pip install pyttsx3 pydub
python tests/generate_test_audio.py

# 2. Start server (in one terminal)
python backend/main.py

# 3. Run API test (in another terminal)
python tests/test_api.py
```

## Expected Results

### Component Tests (test_phase1.py)

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
```

### API Test (test_api.py)

```
QUALITY CHECKS
================================================================================
✅ All SOAP sections present
✅ Average confidence >= 0.70
✅ Entity provenance present
✅ Processing time < 120s

Quality Score: 4/4 checks passed

🎉 ALL CHECKS PASSED!
```

## Troubleshooting

### "GROQ_API_KEY not configured"

**Solution:** Edit `.env` file with actual Groq API key from https://console.groq.com

### "HuggingFace token error"

**Solution:**
1. Set `HF_TOKEN` in `.env`
2. Accept terms at: https://huggingface.co/pyannote/speaker-diarization-3.1
3. Wait 5 minutes for access to propagate

### "Server is not running"

**Solution:** Start server in separate terminal:
```bash
python backend/main.py
```

### "Test audio file not found"

**Solution:** Generate test audio first:
```bash
python tests/generate_test_audio.py
```

### Models taking too long

**First run:** Models download and cache (30-60 seconds)
**Subsequent runs:** Models load from cache (10-20 seconds)

**Solution:** Be patient on first run. Use smaller Whisper model if needed:
```
# In .env
WHISPER_MODEL=tiny  # or base, small
```

## Test Coverage

### Phase 1 Coverage

- ✅ Audio transcription (Whisper)
- ✅ Speaker diarization (Pyannote)
- ✅ Clinical relevance filtering
- ✅ Entity extraction with provenance
- ✅ SOAP note generation
- ✅ API endpoint
- ✅ Error handling
- ✅ Configuration management

### Not Yet Covered (Future Phases)

- ⏳ OCR test report extraction (Phase 3)
- ⏳ RAG guideline retrieval (Phase 2)
- ⏳ QA Guardrail validation (Phase 2)
- ⏳ Clinical Safety Guardrail (Phase 2)
- ⏳ Confidence routing (Phase 2)
- ⏳ Human handoff mechanisms (Phase 5)
- ⏳ Database persistence (Phase 4)
- ⏳ Frontend UI (Phase 6)

## Manual Testing

### Using curl

```bash
curl -X POST http://localhost:8000/api/consultation \
  -F "audio_file=@tests/test_consultation.wav" \
  | jq '.'
```

### Using Python requests

```python
import requests

with open('tests/test_consultation.wav', 'rb') as f:
    files = {'audio_file': f}
    response = requests.post(
        'http://localhost:8000/api/consultation',
        files=files
    )
    
print(response.json())
```

### Using Postman

1. Method: POST
2. URL: `http://localhost:8000/api/consultation`
3. Body: form-data
4. Key: `audio_file` (type: file)
5. Value: Select `test_consultation.wav`

## Quality Criteria

All tests must pass these criteria:

1. **Functional**: All components work without errors
2. **Performance**: Processing < 120 seconds
3. **Quality**: Average confidence >= 0.70
4. **Completeness**: All SOAP sections present
5. **Provenance**: All entities have source/speaker/utterance

## Next Steps

After all Phase 1 tests pass:

1. Implement Phase 2 (RAG + Guardrails)
2. Add Phase 2 test suite
3. Implement Phase 3 (OCR)
4. Add integration tests
5. Add performance benchmarks
6. Add stress tests

## Documentation

See [`docs/TESTING.md`](../docs/TESTING.md) for comprehensive testing guide.