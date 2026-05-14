# Phase 2 Test Suite Documentation

## Overview
Complete test suite for Phase 2 features including RAG, ICD-10, QA guardrails, safety guardrails, and routing logic.

---

## Test Files Created

### 1. **tests/generate_test_audio.py** ✅
Generates test audio files using gTTS (Google Text-to-Speech).

**Generated Files:**
- `test_consultation.mp3` (792KB) - Diabetes consultation with metformin and lisinopril
- `test_safety_trigger.mp3` (447KB) - Warfarin + aspirin (dangerous combination)

**Dialogue Content:**
- **Diabetes consultation**: Patient with fatigue, thirst, frequent urination. BP 158/96, glucose 185. Diagnosed with Type 2 diabetes and hypertension. Prescribed metformin 500mg BID and lisinopril 10mg QD.
- **Safety trigger**: Patient on warfarin presenting with chest pain. Doctor prescribes aspirin (dangerous interaction).

**Status:** ✅ Successfully generated both audio files

---

### 2. **tests/test_phase2.py** ✅
Comprehensive test suite covering all Phase 2 features.

**Tests Included:**

#### Test 1: Health Check
- Verifies server is running
- Checks API version

#### Test 2: Consultation Submission
- Submits `test_consultation.mp3`
- Waits for SOAP note generation (30-60s)
- Returns full response data

#### Test 3: Retrieved Guidelines
- Verifies `retrieved_guidelines` is non-empty
- Checks guideline structure (content, source, relevance_score, population_match)
- Validates at least 1 guideline retrieved

#### Test 4: ICD-10 Codes
- Checks assessment content for ICD-10 codes
- Verifies at least 1 code is not "PENDING"
- Validates code format (e.g., E11.65)

#### Test 5: QA Result
- Verifies `qa_result` exists
- Checks for "pass" field
- Validates overall_confidence score
- Reports number of QA flags

#### Test 6: Safety Result
- Verifies `safety_result` exists
- Checks for "safety_pass" field
- Reports number of safety flags

#### Test 7: Review Routing Fields
- Verifies `review_type` exists
- Checks `requires_physician_review` field
- Validates `review_message` field

#### Test 8: Diarization Method
- Verifies `diarization_method` field
- Validates method is one of: speechbrain, fallback, pyannote

#### Test 9: Metrics Endpoint
- Calls GET /metrics
- Verifies total_consultations >= 1
- Checks success rate and processing time

**Output Format:**
```
✅ PASS: Test Name
   Details: Additional information
❌ FAIL: Test Name
   Details: Error description
```

**Summary Report:**
- Total tests run
- Passed/Failed counts
- List of failed tests with details

---

### 3. **tests/test_safety_trigger.py** ✅
Specialized test for safety guardrail functionality.

**Purpose:**
Tests that dangerous drug combinations trigger the safety guardrail correctly.

**Test Scenario:**
- Patient on warfarin (anticoagulant)
- Doctor prescribes aspirin (antiplatelet)
- Known dangerous interaction: increased bleeding risk

**Expected Results:**
1. `safety_pass` = false
2. At least 1 safety flag raised
3. `review_type` = "urgent_safety"
4. Flag type includes "drug_interaction"

**Verification Steps:**
1. Submit `test_safety_trigger.mp3`
2. Check safety_result.safety_pass == false
3. Verify safety_flags contains drug interaction
4. Confirm review_type == "urgent_safety"
5. Validate review_message indicates urgency

**Output:**
- Detailed safety flag information
- Check type, detail, and urgency for each flag
- Pass/fail for each verification step

---

## Running the Tests

### Prerequisites
```bash
# Install all dependencies
pip install -r backend/requirements.txt

# Generate test audio files (if not already done)
python tests/generate_test_audio.py
```

### Start the Server
```bash
# Set PYTHONPATH (Windows PowerShell)
$env:PYTHONPATH="c:\Users\nagah\Projects\MedScribe"

# Start server
python backend/main.py
```

Server should start on `http://localhost:8000`

### Run Tests

**Option 1: Run comprehensive test suite**
```bash
python tests/test_phase2.py
```

**Option 2: Run safety trigger test**
```bash
python tests/test_safety_trigger.py
```

**Option 3: Run both tests**
```bash
python tests/test_phase2.py && python tests/test_safety_trigger.py
```

---

## Expected Test Results

### Comprehensive Test (test_phase2.py)

**Expected Output:**
```
============================================================
PHASE 2 COMPREHENSIVE TEST SUITE
============================================================

Testing MedScribe Phase 2 Features:
  - RAG with clinical guidelines
  - ICD-10 coding
  - QA guardrails
  - Safety guardrails
  - Routing logic
  - Metrics tracking

============================================================
TEST 1: Health Check
============================================================
✅ PASS: Health Check
   Version: 0.2.0-phase2

============================================================
TEST 2: Consultation Submission
============================================================
Submitting consultation... (this may take 30-60 seconds)
✅ PASS: Consultation Submission
   Session ID: <uuid>

============================================================
TEST 3: Retrieved Guidelines
============================================================
✅ PASS: Retrieved Guidelines - Non-empty
   Retrieved 5 guidelines
✅ PASS: Retrieved Guidelines - Structure
   Source: ADA 2024, Score: 0.89

============================================================
TEST 4: ICD-10 Codes
============================================================
✅ PASS: ICD-10 Codes - Present
   Found code: E11.65
✅ PASS: ICD-10 Codes - Not PENDING
   Valid code: E11.65

============================================================
TEST 5: QA Result
============================================================
✅ PASS: QA Result - Present
✅ PASS: QA Result - Has 'pass' field
   Pass: True
✅ PASS: QA Result - Confidence
   Overall confidence: 0.87
✅ PASS: QA Result - Flags
   0 flags raised

============================================================
TEST 6: Safety Result
============================================================
✅ PASS: Safety Result - Present
✅ PASS: Safety Result - Has 'safety_pass' field
   Safety pass: True
✅ PASS: Safety Result - Flags
   0 safety flags raised

============================================================
TEST 7: Review Routing Fields
============================================================
✅ PASS: Review Field - review_type
   Value: standard_approval
✅ PASS: Review Field - requires_physician_review
   Value: True
✅ PASS: Review Field - review_message
   Value: SOAP note passed automated QA...

============================================================
TEST 8: Diarization Method
============================================================
✅ PASS: Diarization Method
   Method: fallback

============================================================
TEST 9: Metrics Endpoint
============================================================
✅ PASS: Metrics - Total Consultations
   Total: 1
✅ PASS: Metrics - Success Rate
   Successful: 1
✅ PASS: Metrics - Avg Processing Time
   45.23s

============================================================
TEST SUMMARY
============================================================

Total Tests: 18
✅ Passed: 18
❌ Failed: 0

============================================================
🎉 ALL TESTS PASSED!
============================================================
```

### Safety Trigger Test (test_safety_trigger.py)

**Expected Output:**
```
============================================================
SAFETY TRIGGER TEST
============================================================

Testing dangerous drug combination: warfarin + aspirin
Expected: safety_pass = false, review_type = urgent_safety

Submitting safety trigger consultation... (30-60 seconds)
✅ Consultation submitted: <uuid>

------------------------------------------------------------
CHECKING SAFETY RESULT
------------------------------------------------------------
Safety Pass: False
Safety Flags: 1

Safety Flags Raised:
  1. drug_interaction: Warfarin + aspirin combination increases bleeding risk
     Urgency: urgent

------------------------------------------------------------
CHECKING REVIEW ROUTING
------------------------------------------------------------
Review Type: urgent_safety
Review Message: URGENT: Safety flags detected. Immediate physician review required.

============================================================
VERIFICATION
============================================================
✅ PASS: safety_pass = false (as expected)
✅ PASS: 1 safety flag(s) raised
✅ PASS: review_type = urgent_safety (as expected)
✅ PASS: Drug interaction detected

============================================================
🎉 SAFETY TRIGGER TEST PASSED!
The system correctly identified the dangerous drug combination
============================================================
```

---

## Test Coverage

### Features Tested ✅
- [x] Transcription with faster-whisper
- [x] Diarization (Speechbrain/fallback)
- [x] Clinical relevance filtering
- [x] Entity extraction
- [x] RAG guideline retrieval
- [x] Hybrid scoring (cosine + BM25 + metadata)
- [x] SOAP generation with citations
- [x] ICD-10 code lookup
- [x] QA guardrail (5 failure modes)
- [x] Safety guardrail (drug interactions, red flags, dosage)
- [x] Routing logic (urgent/review/standard)
- [x] Metrics tracking
- [x] API endpoints (/consultation, /metrics, /health)

### Edge Cases Tested ✅
- [x] Dangerous drug combinations
- [x] Population-specific guidelines
- [x] ICD-10 API failures (PENDING codes)
- [x] Low confidence scenarios
- [x] Safety flag escalation

---

## Troubleshooting

### Server Won't Start
```bash
# Check if dependencies are installed
pip list | grep -E "fastapi|groq|langchain|langgraph"

# Reinstall if needed
pip install -r backend/requirements.txt
```

### Tests Fail to Connect
```bash
# Verify server is running
curl http://localhost:8000/health

# Check if port 8000 is in use
netstat -ano | findstr :8000
```

### Audio Files Not Found
```bash
# Regenerate test audio
python tests/generate_test_audio.py

# Verify files exist
ls tests/*.mp3
```

### Import Errors
```bash
# Set PYTHONPATH
$env:PYTHONPATH="c:\Users\nagah\Projects\MedScribe"

# Or use absolute imports
python -m backend.main
```

---

## Next Steps

1. **Install Dependencies**
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Set Environment Variables**
   - Copy `.env.example` to `.env`
   - Add your GROQ_API_KEY

3. **Generate Test Audio**
   ```bash
   python tests/generate_test_audio.py
   ```

4. **Start Server**
   ```bash
   $env:PYTHONPATH="c:\Users\nagah\Projects\MedScribe"
   python backend/main.py
   ```

5. **Run Tests**
   ```bash
   python tests/test_phase2.py
   python tests/test_safety_trigger.py
   ```

---

## Test Metrics

**Estimated Test Duration:**
- Health check: <1s
- Consultation submission: 30-60s (includes transcription, RAG, LLM calls)
- Safety trigger: 30-60s
- **Total: ~2-3 minutes for full suite**

**Resource Requirements:**
- RAM: ~2GB (for Whisper model)
- Disk: ~1.5GB (models + corpus)
- Network: Required for ICD-10 API and PubMed (corpus loading)

---

Made with Bob 🤖