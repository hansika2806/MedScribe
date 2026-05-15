# Phase 4 Testing and Debugging Guide

This guide explains how to test Phase 4 and how to debug the failures that appeared during the implementation session.

## Prerequisites

Start the backend from the repository root:

```powershell
python -m backend.main
```

Required environment variables:

```text
GROQ_API_KEY=...
HF_TOKEN=...
LLM_MODEL=llama-3.3-70b-versatile
LLM_MAX_TOKENS=2048
```

The sample Phase 4 test uses:

```text
tests/test_consultation.wav
tests/pdfs/sample_lab_report.pdf
```

If the PDF is missing, `tests/test_phase4.py` calls the local PDF fixture generator.

## Main Test Command

Run:

```powershell
python tests/test_phase4.py
```

This performs four checks:

1. Direct OCR extraction from the sample PDF.
2. Full API run with audio plus PDF.
3. Full API run with audio only.
4. Performance log validation for expected graph nodes.

The test can take several minutes on first model load.

## Expected Test Output

The test should print an OCR section like:

```text
OCR EXTRACTION
{
  "HbA1c": {
    "value": "8.2",
    "source": "ocr",
    "verified": true,
    "flag": null
  }
}
```

Then it should print API results:

```text
API WITH PDF
Session: ...
OCR method: paddleocr
...

API WITHOUT PDF
Session: ...
OCR method: no_pdf
```

Finally:

```text
PHASE 4 TEST SUMMARY
All Phase 4 checks passed.
```

## Manual API Test With PDF

Using PowerShell:

```powershell
$audio = "tests/test_consultation.wav"
$pdf = "tests/pdfs/sample_lab_report.pdf"
curl.exe -X POST "http://localhost:8000/consultation" `
  -F "audio_file=@$audio;type=audio/wav" `
  -F "pdf_file=@$pdf;type=application/pdf"
```

Check these response fields:

```json
{
  "status": "completed",
  "ocr_method": "paddleocr",
  "ocr_page_count": 1,
  "extracted_lab_values": {},
  "lab_values": [],
  "review_type": "standard_approval"
}
```

The exact `review_type` can vary depending on QA and safety results.

## Manual API Test Without PDF

```powershell
$audio = "tests/test_consultation.wav"
curl.exe -X POST "http://localhost:8000/consultation" `
  -F "audio_file=@$audio;type=audio/wav"
```

Expected OCR fields:

```json
{
  "ocr_method": "no_pdf",
  "ocr_page_count": 0,
  "extracted_lab_values": {}
}
```

## Performance Logs

Phase 4 writes node and session logs to:

```text
data/performance_logs.jsonl
```

You can inspect them through the API:

```powershell
curl.exe "http://localhost:8000/performance/{session_id}"
```

Expected nodes:

```text
transcribe
clinical_relevance_filter
clinical_extractor
rag
soap
icd10
qa_guardrail
safety_guardrail
```

If the terminal appears stuck, performance logs and backend logs tell you whether the system is actually processing Whisper, diarization, LLM calls, RAG, or validation.

## Debugging: Test Appears Stuck

### Symptom

OCR output prints, then nothing appears for a long time.

### Likely Cause

The pipeline is still running expensive stages:

- Whisper transcription
- SpeechBrain model load or fallback diarization
- LLM filtering
- LLM extraction
- RAG retrieval
- SOAP generation
- QA and safety checks

### What To Check

1. Backend terminal logs.
2. `data/performance_logs.jsonl`.
3. `/performance/{session_id}` after the request completes.

### Fix Pattern

Keep stage logs before long calls. For future work, consider async job status updates per graph node.

## Debugging: False OCR Extraction

### Symptom

OCR extracts a wrong value such as:

```json
"Hemoglobin": "138"
```

### Likely Cause

Regex patterns matched a nearby numeric value from a report table.

### What To Check

1. `ocr_result.raw_text`.
2. The relevant regex in `backend/tools/ocr.py`.
3. Whether the pattern allows too many unrelated characters between label and value.

### Fix Pattern

Tighten the pattern around the label and expected unit. Prefer narrower matching over broad table-spillover matching.

## Debugging: 500 After PDF Upload

### Symptom

The API returns:

```text
500 Server Error
```

### Common Cause

Schema mismatch between OCR output and downstream Pydantic models.

Example:

```text
ocr
```

must become:

```text
ocr_only
```

### What To Check

1. API error detail.
2. Backend traceback.
3. `filter.py` source normalization.
4. `extractor.py` OCR lab normalization.
5. `soap.py` entity provenance normalization.

## Debugging: JSON Parse Error

### Symptom

```text
JSON parse error: Extra data
```

### Likely Cause

The LLM returned clean JSON plus additional prose or Markdown.

### What To Check

1. Log the first 1000 characters of the LLM response.
2. Confirm the node uses `extract_json_from_response()`.
3. Confirm the response contains at least one valid JSON object.

### Fix Pattern

Extract first valid JSON object and normalize before Pydantic validation.

## Debugging: Token Limit Error

### Symptom

```text
Error 413
Request too large
```

### Likely Cause

SOAP prompt context became too large.

### What To Check

1. Number of extracted entities.
2. Number of guideline snippets.
3. Size of SOAP system prompt.
4. Current `LLM_MODEL`.
5. Current `LLM_MAX_TOKENS`.

### Fix Pattern

Use compact JSON, limit guideline excerpts, limit entity lists, and keep the stronger clinical model where possible.

## Debugging: SpeechBrain Windows Permission Error

### Symptom

```text
WinError 1314
A required privilege is not held by the client
```

### Likely Cause

SpeechBrain or HuggingFace cache behavior attempted an operation restricted by Windows permissions.

### Expected Behavior

The diarization tool should fall back to simpler diarization. This can be noisy in logs but does not always mean the consultation failed.

### What To Check

1. `diarization_method` in the response.
2. Whether transcript and SOAP generation still completed.
3. Performance logs for the `transcribe` node.

## Debugging: Missing `filtered_utterances`

### Symptom

```text
Response missing 'filtered_utterances'
```

### Likely Cause

The LLM returned an alias such as:

```text
results
items
utterances
filtered_transcript
```

### Fix Pattern

Normalize aliases in `filter.py` before constructing `FilteredTranscript`.

## Debugging: No SOAP Note

### Symptom

```text
No SOAP note generated
```

### Likely Causes

- filter returned no usable utterances
- extractor returned no meaningful clinical data
- SOAP JSON could not be extracted
- SOAP validation failed

### What To Check

1. Was `filtered_transcript` present?
2. Did `extracted_entities` contain symptoms, medications, vitals, or labs?
3. Did OCR labs merge into `lab_values`?
4. Did `soap.py` create fallback sections?
5. Did `state["error"]` get set before SOAP?

## Debugging: OCR Entity Validation Error

### Symptom

```text
utterance: null
Input should be a valid string
```

### Likely Cause

An OCR-derived entity did not have spoken provenance.

### Fix Pattern

SOAP entity normalization should convert missing OCR utterances into:

```text
OCR extracted value: {claim}
```

## Quick Debug Checklist

Use this order when diagnosing Phase 4:

1. Health check: `GET /health`.
2. Confirm PDF exists and opens.
3. Run direct OCR test.
4. Run API with PDF.
5. Inspect `ocr_method` and `extracted_lab_values`.
6. Inspect backend logs for the first node that failed.
7. Inspect `/performance/{session_id}`.
8. Check schema normalization at the failed node.
9. Check whether the failure should become physician review instead of a hard crash.

## Regression Areas To Protect

When changing Phase 4 code, re-test:

- audio-only consultation still works
- PDF consultation works
- OCR failure does not crash audio-only flow
- source labels normalize consistently
- malformed LLM JSON is tolerated
- OCR lab values survive into extracted entities
- SOAP objective can include OCR labs
- QA flags missing provenance
- safety routing still runs after OCR integration
- performance logs include every major node
