# Phase 6 and Phase 7 Plan - Proper Diarization, Accuracy, Polish, and Demo

## Why This Document Exists

Phases 1 through 5 created a working MedScribe prototype:

- Audio upload
- faster-whisper transcription
- Speechbrain/fallback diarization
- Clinical filtering
- Entity extraction
- RAG
- SOAP generation
- OCR PDF support
- SQLite persistence
- JWT login
- Physician review and approval UI

The remaining weak point is speaker diarization. The current fallback can alternate Doctor/Patient mechanically, which can confuse downstream clinical logic. The Clinical Relevance Filter currently has a defensive bypass when too few utterances are included. That bypass keeps the system from failing, but it also means the filter is less selective than originally intended.

Phase 6 focuses on real diarization and filter accuracy.

Phase 7 focuses on final demo polish, performance, repository cleanup, and presentation readiness.

---

## Current State After Phase 5

### What Works

- Backend starts successfully.
- `/health` returns `0.5.0-phase5`.
- Frontend login works.
- JWT-protected endpoints work.
- Upload/review/approve workflow works.
- Speechbrain can import and logs availability.
- If Speechbrain fails, fallback alternating diarization keeps the app usable.
- FFmpeg PATH is set automatically on backend startup.
- Phase 5 docs and troubleshooting are in place.

### What Is Still Weak

1. Real diarization is not yet trustworthy enough for the final clinical demo.
2. Current diarization implementation uses Speechbrain embeddings plus simple silence segmentation.
3. Speaker labels are assigned with an assumption: first cluster equals Doctor.
4. Sentence-to-segment alignment is rough.
5. Fallback alternating diarization can assign symptoms to Doctor and prescriptions to Patient.
6. Clinical Relevance Filter bypasses itself when fewer than two utterances are included.
7. Some docs still mention pyannote as the intended diarization system, while current code is Speechbrain/fallback.

### Execution Update - Phase 6 Implementation Started

The first Phase 6 implementation pass has now been applied:

- `pyannote.audio==3.3.2` added to backend requirements.
- `backend/tools/diarization.py` refactored into pyannote primary, Speechbrain secondary, deterministic fallback last.
- faster-whisper now returns timestamped segments for overlap-based speaker assignment.
- diarization timestamps now include method metadata such as `pyannote|0.00-2.80|SPEAKER_00`.
- Doctor/Patient mapping now uses a deterministic role-language classifier instead of only assuming first speaker.
- Clinical Relevance Filter broad bypass was replaced with keyword rescue plus last-resort include-all only when fallback diarization is active.
- `tests/test_pyannote_compat.py` added.
- `tests/test_phase6_diarization.py` added.
- `tests/diarization/README.md` added for labeled real-audio fixtures.
- SOAP review now shows whether real diarization or fallback was used.

Still required to complete Phase 6:

- Install the new pyannote dependency in the active venv.
- Confirm HuggingFace token and model terms.
- Run pyannote compatibility test.
- Add labeled real doctor-patient audio fixtures.
- Run Phase 6 diarization accuracy test.

### Current Relevant Files

```text
backend/tools/diarization.py
backend/pipeline/graph.py
backend/pipeline/nodes/filter.py
backend/models/schemas.py
backend/config.py
backend/requirements.txt
backend/monitoring.py
docs/BUGFIX_DIARIZATION.md
docs/PHASE4_SCHEMA_AND_FALLBACKS.md
docs/PHASE5_IMPLEMENTATION.md
docs/TROUBLESHOOTING.md
docs/WORKFLOW.md
tests/test_api.py
tests/test_phase4.py
tests/test_phase5.py
tests/audio/
```

---

## Phase 6 Goal

Implement proper speaker diarization so MedScribe can reliably identify Doctor and Patient turns from real consultation audio.

The target is not merely "no crash." The target is:

- Accurate turn boundaries.
- Correct speaker grouping.
- Stable Doctor/Patient label assignment.
- Confidence scores that downstream nodes can trust.
- Clinical Relevance Filter no longer needing broad bypass behavior.
- Measurable improvement on real doctor-patient audio.

---

## Phase 6 Scope

### In Scope

- Resolve pyannote-audio and HuggingFace dependency compatibility.
- Add a pyannote diarization path.
- Keep Speechbrain as secondary fallback.
- Keep deterministic fallback only as last resort.
- Add diarization method selection and clear logs.
- Add diarization-specific tests.
- Add real audio test set and expected speaker labels.
- Improve Clinical Relevance Filter behavior once diarization is reliable.
- Update docs to reflect actual diarization behavior.

### Out of Scope

- Production cloud deployment.
- Replacing faster-whisper.
- Real EHR integration.
- Real physician database.
- HTTPS and SSL.
- Multi-user production auth hardening.
- Full medical-grade diarization validation study.

---

## Phase 6 Architecture Decision

### Preferred Diarization Stack

Use this priority order:

```text
1. pyannote-audio pipeline
2. Speechbrain embedding clustering
3. Deterministic fallback
```

Why:

- pyannote is built specifically for speaker diarization.
- Speechbrain ECAPA is a speaker embedding model, not a full diarization pipeline.
- Deterministic fallback is useful for resilience, but clinically weak.

### Why Not Remove Fallback Completely

The app should never fail just because diarization fails. Instead:

- If pyannote works, use it.
- If pyannote fails, try Speechbrain.
- If Speechbrain fails, use fallback but clearly mark diarization as unavailable.
- If fallback is used, UI and QA should make speaker attribution uncertainty visible.

Fallback remains as a safety net, not the normal path.

---

## Phase 6 Task List

## Task 1 - Dependency Compatibility Investigation

### Problem

Earlier pyannote attempts failed because of version mismatch:

```text
hf_hub_download() got an unexpected keyword argument 'use_auth_token'
```

Known history from docs:

- `pyannote.audio==3.1.1` used older auth paths.
- Newer `huggingface_hub` changed token handling.
- Downgrading `huggingface_hub` helped one error but caused other compatibility issues.
- Some pyannote models require explicit HuggingFace access approval.

### Work

Create a small isolated compatibility test before touching the main pipeline.

Recommended test file:

```text
tests/test_pyannote_compat.py
```

It should test:

1. Import pyannote.
2. Import HuggingFace Hub.
3. Confirm `HF_TOKEN` is loaded.
4. Load configured diarization model.
5. Run model against one short test audio file.
6. Print package versions and clear PASS/FAIL messages.

### Candidate Version Sets

Try one version set at a time.

#### Candidate A - Conservative pyannote 3.1 path

```text
pyannote.audio==3.1.1
huggingface_hub==0.19.4
```

Reason: old docs say this was the closest match for `use_auth_token`.

Risk: other installed packages may need newer HuggingFace Hub.

#### Candidate B - Modern pyannote path

```text
pyannote.audio>=3.3.0
huggingface_hub compatible with that pyannote release
```

Reason: newer pyannote versions are more likely to support modern `token=` behavior.

Risk: may require newer Torch, which could disturb current Whisper/Speechbrain stack.

#### Candidate C - Pin-free local experiment

Use a separate throwaway venv to discover the compatible set:

```bat
cd C:\Users\nagah\Projects\MedScribe
python -m venv venv-pyannote-test
venv-pyannote-test\Scripts\activate
pip install pyannote.audio
pip freeze > pyannote-freeze.txt
```

Reason: protects the working Phase 5 venv.

### Acceptance Criteria

- A selected version set is documented.
- `pip install -r backend/requirements.txt` works.
- Backend still starts.
- pyannote model loads with `HF_TOKEN`.
- No `use_auth_token` error.
- No model access error.

---

## Task 2 - HuggingFace Access Checklist

### Required Access

The user must log in to HuggingFace and accept model terms for all required pyannote models.

Likely required:

```text
pyannote/speaker-diarization-3.1
pyannote/segmentation-3.0
```

Depending on the selected pyannote version, more model gates may appear.

### Required Environment

`.env` must contain:

```text
HF_TOKEN=your_huggingface_token
DIARIZATION_MODEL=pyannote/speaker-diarization-3.1
```

### Test Command

```bat
cd C:\Users\nagah\Projects\MedScribe
venv\Scripts\activate
python tests\test_pyannote_compat.py
```

### Acceptance Criteria

- Token is found.
- Model terms are accepted.
- Model loads.
- If access is missing, the test prints the exact model URL to approve.

---

## Task 3 - Refactor Diarization Service

### Current Problem

`backend/tools/diarization.py` currently mixes:

- Speechbrain model loading
- silence segmentation
- embedding extraction
- clustering
- fallback diarization
- final diarization entrypoint

This makes it harder to add pyannote cleanly.

### Target Design

Refactor into three strategy classes:

```text
PyannoteDiarizer
SpeechbrainDiarizer
FallbackDiarizer
```

Shared public entrypoint:

```python
def diarize(audio_path: str, transcript: str) -> DiarizedTranscript:
    ...
```

Suggested behavior:

```text
try pyannote
  if success -> return diarized transcript, method pyannote
try Speechbrain
  if success -> return diarized transcript, method speechbrain
return deterministic fallback, method fallback
```

### Required Logging

Every run must log:

```text
Diarization method selected: pyannote
```

or:

```text
Diarization method selected: speechbrain
```

or:

```text
Diarization method selected: fallback alternating
```

Also log:

- model load success/failure
- number of speaker turns
- number of final utterances
- average speaker confidence
- why a method failed before fallback

### Acceptance Criteria

- Existing pipeline code still calls `diarize(...)`.
- API response still returns `diarization_method`.
- Metrics still count method usage.
- Fallback still works if pyannote/Speechbrain fail.

---

## Task 4 - Proper Timestamp Alignment

### Current Problem

The current Speechbrain path splits transcript text by periods and aligns sentences to audio segments by index. That is fragile.

### Desired Behavior

Use timestamped Whisper segments instead of plain transcript text where possible.

Target data shape:

```json
[
  {
    "start": 0.3,
    "end": 4.2,
    "text": "Good morning, what brings you in today?"
  }
]
```

Then assign each segment to the diarized speaker turn with the largest time overlap.

### Needed Code Areas

```text
backend/tools/whisper.py
backend/tools/diarization.py
backend/models/schemas.py
backend/pipeline/graph.py
```

### Alignment Algorithm

For each Whisper segment:

1. Read segment start/end.
2. Compare to each diarization turn start/end.
3. Choose speaker with highest overlap.
4. If overlap is below threshold, mark speaker as `uncertain`.
5. Use overlap ratio as confidence input.

Pseudo:

```text
overlap = max(0, min(seg.end, turn.end) - max(seg.start, turn.start))
ratio = overlap / segment_duration
```

### Acceptance Criteria

- Utterance timestamps are real times, not sentence indexes.
- Long sentences are not blindly matched to the wrong speaker.
- Low-overlap segments become `uncertain`.
- Clinical filter can use real confidence.

---

## Task 5 - Stable Doctor/Patient Label Assignment

### Current Problem

Even real diarization usually returns labels like:

```text
SPEAKER_00
SPEAKER_01
```

It does not know which one is Doctor or Patient.

### Options

#### Option A - First Speaker Is Doctor

Assumption:

```text
The doctor starts the consultation.
```

Pros:

- Simple.
- Often true in clinic recordings.

Cons:

- Fails if patient starts speaking first.

#### Option B - LLM Role Classifier

After diarization, classify each speaker cluster based on language:

Doctor-like:

- "What brings you in?"
- "I will prescribe..."
- "Your blood pressure is..."
- "Follow up..."

Patient-like:

- "I feel..."
- "My pain..."
- "I have been taking..."
- "My father had..."

Pros:

- More robust.

Cons:

- Extra LLM call.
- Can fail on very short audio.

#### Option C - Hybrid

Use first-speaker assumption, then validate with role-language classifier.

Recommended:

```text
Use Option C.
```

### Proposed Implementation

Add:

```text
backend/pipeline/nodes/speaker_role_classifier.py
```

or keep it inside `backend/tools/diarization.py` first if scope needs to stay small.

Output:

```json
{
  "SPEAKER_00": "Doctor",
  "SPEAKER_01": "Patient",
  "confidence": 0.88,
  "reason": "SPEAKER_00 asks clinical questions and gives plan instructions"
}
```

### Acceptance Criteria

- Doctor/Patient mapping is not purely random.
- Low-confidence mapping marks uncertain utterances.
- Logs explain the mapping decision.
- Test audio with doctor first and patient first both pass.

---

## Task 6 - Replace Broad Clinical Filter Bypass

### Current Problem

In `backend/pipeline/nodes/filter.py`, if the LLM includes fewer than two utterances, the code bypasses the filter and includes all utterances:

```python
if included_count < 2:
    # Bypassing filter - passing ALL utterances to Clinical Extractor
```

This was necessary when diarization was weak. With better diarization, this should become narrower.

### Desired Behavior

Replace broad bypass with a smarter rescue strategy:

1. Detect whether low inclusion is caused by diarization uncertainty.
2. If diarization is real and confidence is high, trust the filter.
3. If diarization is fallback or low confidence, run deterministic clinical keyword rescue.
4. Mark rescued utterances as `speaker_uncertain` if needed.
5. Route low-confidence notes to review instead of pretending everything is normal.

### Deterministic Rescue Keywords

Include utterances with:

```text
pain, fever, cough, breath, dizziness, nausea, vomiting,
headache, chest, sugar, glucose, pressure, BP, HbA1c,
tablet, medicine, medication, prescribe, start, stop,
continue, increase, decrease, follow up, diagnosis,
diabetes, hypertension, asthma, infection
```

### Acceptance Criteria

- No unconditional "include all" except as last-resort failure fallback.
- Filter preserves meaningful exclusion of greetings and small talk.
- If fallback diarization is used, output clearly signals speaker uncertainty.
- Clinical extractor receives fewer irrelevant utterances.

---

## Task 7 - Real Doctor-Patient Audio Test Set

### Current Problem

Synthetic audio and generated scripts are useful but not enough to validate diarization.

### Required Test Set

Create:

```text
tests/diarization/
  audio/
    doctor_first_clear.wav
    patient_first_clear.wav
    overlap_short.wav
    noisy_clinic.wav
    single_speaker_doctor_summary.wav
  labels/
    doctor_first_clear.json
    patient_first_clear.json
    overlap_short.json
    noisy_clinic.json
    single_speaker_doctor_summary.json
```

Label format:

```json
{
  "audio_file": "doctor_first_clear.wav",
  "turns": [
    {
      "start": 0.0,
      "end": 2.8,
      "speaker": "Doctor",
      "text": "Good morning, what brings you in today?"
    },
    {
      "start": 2.9,
      "end": 7.1,
      "speaker": "Patient",
      "text": "I have had chest pain for three days."
    }
  ]
}
```

### Test Metrics

At minimum:

- speaker label accuracy
- turn count difference
- percentage of uncertain turns
- diarization method used
- downstream extraction sanity check

Optional:

- diarization error rate (DER)
- confusion matrix by speaker

### Acceptance Criteria

- At least 5 real or realistic audio samples.
- At least 80 percent speaker-label accuracy on clear two-speaker samples.
- Fallback method is not used on clear samples.
- Clinical extractor correctly attributes symptoms to Patient and plans to Doctor.

---

## Task 8 - Phase 6 Test Script

Create:

```text
tests/test_phase6_diarization.py
```

It should print clear PASS/FAIL lines:

```text
PASS: pyannote compatibility
PASS: model loaded
PASS: doctor_first_clear used pyannote
PASS: doctor_first_clear speaker accuracy 0.86
PASS: patient_first_clear speaker accuracy 0.82
PASS: clinical filter did not trigger broad bypass
PASS: symptoms attributed to Patient
PASS: prescriptions attributed to Doctor
```

If pyannote is unavailable:

```text
FAIL: pyannote compatibility - model access missing
```

Do not silently pass by using fallback. The whole point of Phase 6 is to prove real diarization works.

### Acceptance Criteria

- Test distinguishes pyannote success from fallback success.
- Test can be run independently.
- Test results are saved to:

```text
tests/phase6_diarization_results.json
```

---

## Task 9 - Metrics and UI Visibility

### Backend Metrics

Current metrics already track:

```text
diarization_method_used
```

Enhance metrics with:

```text
average_speaker_confidence
uncertain_utterance_count
speaker_role_mapping_confidence
filter_bypass_count
clinical_keyword_rescue_count
```

### Frontend Review UI

Show diarization quality in SOAP review:

```text
Diarization: pyannote
Speaker confidence: 91%
Uncertain turns: 1
```

If fallback:

```text
Diarization: fallback
Speaker attribution is uncertain. Please review provenance carefully.
```

### Acceptance Criteria

- Demo user can see whether real diarization was used.
- Fallback is transparent, not hidden.
- Metrics prove Phase 6 improvement.

---

## Phase 6 Acceptance Criteria

Phase 6 is complete only when all are true:

- Backend starts with pyannote dependencies installed.
- Pyannote model loads from HuggingFace with token.
- Clear two-speaker test audio uses `diarization_method = "pyannote"`.
- Fallback is not used for clear test audio.
- Doctor/Patient labels are correct on at least 80 percent of labeled turns.
- Clinical Relevance Filter no longer relies on broad include-all bypass for clear test audio.
- Patient symptoms are extracted from Patient turns.
- Doctor prescriptions/plans are extracted from Doctor turns.
- Phase 6 test script prints PASS/FAIL results.
- Documentation is updated to remove stale "pyannote already works" claims.

---

# Phase 7 Plan - Polish and Demo

## Phase 7 Goal

Prepare MedScribe for a clean demo and GitHub handoff after proper diarization works.

Phase 7 should make the app feel stable, understandable, and presentable. It is not about adding big new clinical features.

---

## Phase 7 Task List

## Task 1 - Error Handling Improvements

### Backend

Standardize API error shape:

```json
{
  "error_code": "GROQ_RATE_LIMIT",
  "message": "AI service is temporarily busy.",
  "session_id": "...",
  "retryable": true
}
```

Recommended error codes:

```text
AUTH_EXPIRED
AUTH_INVALID
GROQ_RATE_LIMIT
GROQ_API_ERROR
WHISPER_FAILED
DIARIZATION_FAILED
OCR_FAILED
NO_CLINICAL_CONTENT
PIPELINE_VALIDATION_ERROR
DATABASE_ERROR
UNKNOWN_ERROR
```

### Frontend

Map error codes instead of matching free-text strings.

### Acceptance Criteria

- User sees simple error messages.
- Developer logs still show detailed causes.
- Retryable errors are marked.

---

## Task 2 - Performance Optimization

### Measure First

Use:

```text
data/performance_logs.jsonl
GET /performance/{session_id}
```

Track:

- transcription duration
- diarization duration
- OCR duration
- LLM filter duration
- extractor duration
- RAG duration
- SOAP duration
- QA duration
- safety duration
- total request duration

### Likely Optimizations

- Cache loaded diarization model.
- Cache loaded Whisper model.
- Avoid repeated ChromaDB corpus checks.
- Reduce LLM prompt size where safe.
- Use smaller model for development.
- Parallelize independent non-LLM setup where possible.

### Acceptance Criteria

- Clear audio-only demo completes in acceptable time.
- PDF + audio demo completes without appearing stuck.
- Performance summary is documented.

---

## Task 3 - Frontend Loading States

Phase 5 added better loading, but Phase 7 should make it demo-grade.

Add:

- upload progress state
- "backend connected" or health precheck
- disabled controls during upload
- clear status if processing exceeds 90 seconds
- "still working" message instead of frozen progress
- retry controls for network failure

### Acceptance Criteria

- User always knows whether the app is uploading, processing, waiting, failed, or ready.
- No button can accidentally double-submit.
- Slow processing still feels alive.

---

## Task 4 - Demo Video Recording Plan

Prepare a 3-5 minute demo.

### Demo Script

1. Open app at `http://localhost:5173`.
2. Login as `dr.sharma`.
3. Show demo credentials briefly.
4. Upload doctor-patient audio.
5. Optional: upload lab PDF.
6. Show processing screen.
7. Show SOAP review.
8. Expand provenance.
9. Show guideline citations.
10. Show QA and safety panels.
11. Approve note.
12. Show success screen.
13. Logout.

### Must Show

- "Copilot, not autopilot" principle.
- Physician approval required.
- Provenance traceability.
- Diarization method, once Phase 6 is fixed.
- OCR lab extraction if PDF is uploaded.

### Acceptance Criteria

- Demo can be completed without manual backend fixes.
- Video has one clean end-to-end run.
- README points to demo assets or instructions.

---

## Task 5 - README Full Setup Instructions

The README should be rewritten after Phase 6/7 to match reality.

Must include:

- project overview
- architecture diagram
- requirements
- Python 3.11 setup
- venv setup
- backend install
- frontend install
- `.env` setup
- Groq API key instructions
- HuggingFace token and model access instructions
- FFmpeg installation/path note
- demo credentials
- run commands
- test commands
- troubleshooting links
- known limitations

### Acceptance Criteria

- A new developer can set up the app from README alone.
- No stale `/api` route references.
- No stale "pyannote works" statements unless Phase 6 confirms it.

---

## Task 6 - GitHub Repository Cleanup

### Keep

```text
backend/
frontend/
docs/
tests/
.env.example
README.md
ARCHITECTURE.md
```

### Ignore or Remove From Git

```text
venv/
frontend/node_modules/
frontend/dist/
data/chroma/
data/models/
data/temp/
data/*.db
data/*.jsonl
data/metrics.json
__pycache__/
*.pyc
.env
```

### Review Generated Files

Current git status showed generated data changes such as:

```text
data/chroma/.../length.bin
data/metrics.json
data/performance_logs.jsonl
```

These should not be committed unless there is a deliberate reason.

### Acceptance Criteria

- `.gitignore` excludes generated/runtime artifacts.
- No secrets committed.
- No venv or node_modules committed.
- Docs are organized and linked.
- Tests are named by phase.

---

## Task 7 - Final Test Matrix

Run before final demo:

```bat
cd C:\Users\nagah\Projects\MedScribe
venv\Scripts\activate
python tests\test_phase5.py
python tests\test_phase6_diarization.py
```

Frontend:

```bat
cd C:\Users\nagah\Projects\MedScribe\frontend
npm run build
npm run dev
```

Manual UI:

- desktop viewport
- 375px mobile viewport
- login
- wrong password
- upload audio only
- upload audio + PDF
- approve
- logout
- expired/fake token behavior

### Acceptance Criteria

- All automated tests pass or known external-limit failures are documented.
- Frontend build passes.
- Manual demo path works.

---

## Recommended Execution Order

Do not start with UI polish. Fix diarization first.

```text
1. Create pyannote compatibility test
2. Resolve dependency pins
3. Confirm HuggingFace model access
4. Refactor diarization service
5. Add timestamp alignment
6. Add Doctor/Patient role mapping
7. Build real audio test set
8. Replace broad filter bypass
9. Add diarization metrics/UI visibility
10. Update README and stale docs
11. Improve frontend loading/error states
12. Optimize performance
13. Clean repository
14. Record demo
```

---

## Phase 6 Implementation Checklist

- [ ] Add `pyannote.audio` dependency after compatibility test.
- [ ] Add `tests/test_pyannote_compat.py`.
- [ ] Confirm `HF_TOKEN` and model access.
- [ ] Refactor `backend/tools/diarization.py`.
- [ ] Add pyannote primary diarizer.
- [ ] Preserve Speechbrain fallback.
- [ ] Preserve deterministic fallback as last resort.
- [ ] Add timestamped Whisper segment support.
- [ ] Add overlap-based speaker assignment.
- [ ] Add Doctor/Patient role mapping.
- [ ] Add `tests/diarization` labeled audio fixtures.
- [ ] Add `tests/test_phase6_diarization.py`.
- [ ] Replace broad filter bypass with keyword rescue.
- [ ] Add diarization metrics.
- [ ] Show diarization method/confidence in frontend.
- [ ] Update stale pyannote/Speechbrain docs.

---

## Phase 7 Implementation Checklist

- [ ] Standardize backend error response shape.
- [ ] Update frontend error mapping to use error codes.
- [ ] Add upload progress and slow-processing states.
- [ ] Prevent double-submit.
- [ ] Use performance logs to identify slow nodes.
- [ ] Optimize model loading and repeated setup.
- [ ] Rewrite README setup instructions.
- [ ] Clean `.gitignore`.
- [ ] Remove generated runtime artifacts from commit plan.
- [ ] Run full automated test matrix.
- [ ] Run desktop and mobile manual checks.
- [ ] Record 3-5 minute demo video.

---

## Final Definition of Done

Phase 6 is done when MedScribe uses real diarization on clear doctor-patient audio and downstream extraction no longer depends on the broad clinical-filter bypass.

Phase 7 is done when the app can be demoed cleanly from setup to approval, the repository is clean, and a new developer can reproduce the setup from README and docs.
