# Phase 4 Implementation - PDF OCR and Clinical Intelligence

Phase 4 changed MedScribe from an audio-only consultation summarizer into a multi-modal clinical intelligence pipeline. The system can now process consultation audio together with optional PDF lab reports, extract objective lab values through OCR, merge those values with transcript-derived clinical context, and use the unified context for SOAP generation, ICD-10 coding, QA validation, safety validation, and physician review.

## Implementation Goal

Before Phase 4, the core pipeline was:

```text
Audio -> transcript -> clinical extraction -> SOAP
```

After Phase 4, the target flow became:

```text
Audio consultation
PDF lab reports
OCR lab values
Transcript entities
Retrieved guidelines
        |
        v
Unified clinical context
        |
        v
SOAP + ICD-10 + QA + safety + physician review
```

The important architectural shift is that downstream nodes no longer reason from the transcript alone. They now receive objective report data, source metadata, verification status, and fallback-safe normalized payloads.

## Files Added or Changed

The Phase 4 implementation is centered on these files:

| File | Responsibility |
| --- | --- |
| `backend/api/routes.py` | Accepts optional `pdf_file`, runs OCR before pipeline invocation, returns OCR metadata and extracted labs. |
| `backend/tools/ocr.py` | Extracts text and lab values from PDFs using PaddleOCR with embedded-text fallback. |
| `backend/pipeline/state.py` | Adds PDF and OCR fields to the LangGraph state. |
| `backend/pipeline/nodes/filter.py` | Passes OCR values to the clinical relevance filter and normalizes filter schema drift. |
| `backend/pipeline/nodes/extractor.py` | Merges OCR lab values into structured extracted entities. |
| `backend/pipeline/nodes/soap.py` | Uses compact prompt context and normalizes SOAP output before Pydantic validation. |
| `backend/pipeline/graph.py` | Adds node-level performance logging for observability. |
| `backend/logging_config.py` | Writes per-node and per-session performance logs. |
| `backend/config.py` | Uses `llama-3.3-70b-versatile` and `LLM_MAX_TOKENS=2048`. |
| `.env.example` | Documents the Phase 4 model and token settings. |
| `tests/test_phase4.py` | Tests OCR extraction, API processing with PDF, API processing without PDF, and performance logs. |

## Pipeline State Additions

Phase 4 added these fields to `PipelineState`:

```python
pdf_path: str
ocr_result: Dict[str, Any]
ocr_method: str
test_report_values: Dict[str, Any]
```

These fields let OCR data travel through the same graph as the transcript data. The goal is not just to extract labs, but to preserve enough context for every later node to know:

- whether a PDF was uploaded
- whether OCR succeeded
- which extraction method was used
- which lab values were available
- whether each value came from OCR, transcript, or both

## API Intake

The consultation endpoint now accepts:

```python
audio_file: UploadFile = File(...)
pdf_file: Optional[UploadFile] = File(None)
session_id: str | None = Form(default=None)
```

When a PDF is uploaded:

1. The backend stores it temporarily under `data/temp`.
2. `process_pdf()` runs before the graph starts.
3. OCR output is placed into the initial pipeline state.
4. The graph receives both transcript and report context.
5. The final API response includes OCR method, page count, extracted lab values, and persisted lab values.

When no PDF is uploaded, the backend still provides a predictable OCR payload:

```json
{
  "test_values": "unavailable",
  "reason": "no_pdf_uploaded",
  "action": "physician_manual_entry",
  "lab_values": {},
  "status": "no_pdf",
  "page_count": 0
}
```

That predictable shape matters. It prevents every downstream node from needing special-case null handling.

## OCR Extraction

OCR lives in `backend/tools/ocr.py`.

The `MedicalOCR` class performs three jobs:

1. Open PDF pages with PyMuPDF.
2. Extract text from rendered page images with PaddleOCR.
3. Fall back to embedded PDF text if OCR returns no usable lines.

It then extracts common medical values with regex patterns. Example output:

```json
{
  "HbA1c": {
    "value": "8.2",
    "source": "ocr",
    "verified": true,
    "flag": null
  },
  "Blood_Glucose_Fasting": {
    "value": "185",
    "source": "ocr",
    "verified": true,
    "flag": null
  }
}
```

The OCR result intentionally includes source and verification fields. In a clinical workflow, the value alone is not enough. A physician needs to know where a finding came from and whether the system treated it as verified or uncertain.

## Clinical Filter Integration

The filter node now receives both:

- diarized transcript utterances
- OCR test report values

The prompt asks the model to:

- include or exclude clinical utterances
- map included utterances to SOAP sections
- flag uncertain speaker attribution
- cross-check verbally mentioned labs against OCR report values
- mark OCR-only values as verified report-derived data

The filter also includes schema normalization because model output can drift. For example, Phase 4 observed outputs using keys such as:

```text
filtered_transcript
utterances
results
items
```

The filter normalizes those variants into:

```json
{
  "filtered_utterances": []
}
```

It also normalizes OCR source labels:

```text
ocr -> ocr_only
```

This prevents a small source-label mismatch from crashing the entire pipeline.

## Clinical Extraction Integration

The extractor now receives OCR values in the prompt and also performs a deterministic merge after the model returns.

This is important because the LLM may omit OCR labs even when they are present in the input. Phase 4 fixed that by merging normalized OCR labs into `entities.lab_values` if they are missing.

Normalized OCR labs use this shape:

```json
{
  "HbA1c": {
    "value": "8.2",
    "source": "ocr_only",
    "verified": true,
    "flag": null
  }
}
```

This gives SOAP generation and QA a stable objective-data contract.

## SOAP Generation Changes

SOAP generation became more complex because the prompt now includes:

- symptoms
- medications
- vitals
- lab values
- family history
- population tag
- guideline snippets
- provenance expectations

To avoid token-limit failures, `backend/pipeline/nodes/soap.py` now compacts prompt JSON and limits context size:

- compact JSON serialization
- bounded entity lists
- only top guideline snippets
- shortened guideline excerpts

The implementation did not solve token pressure by downgrading model quality. Instead, Phase 4 moved to:

```text
LLM_MODEL=llama-3.3-70b-versatile
LLM_MAX_TOKENS=2048
```

That keeps reasoning quality high while still bounding generated output.

SOAP output is normalized before validation. This handles:

- section alias drift such as `S`, `O`, `A`, `P`
- missing SOAP sections
- malformed uncertain spans
- object-shaped guideline citations
- OCR entities with missing utterances
- invalid confidence values

For OCR-derived entities with no spoken sentence, Phase 4 creates an utterance such as:

```text
OCR extracted value: HbA1c 8.2
```

That keeps provenance complete without pretending the lab value was spoken in the consultation.

## Observability

Phase 4 added performance logging because the pipeline can look frozen while running long model and audio operations.

`backend/pipeline/graph.py` wraps major nodes with `_with_performance_logging()`. Logs are written to:

```text
data/performance_logs.jsonl
```

The API also exposes:

```text
GET /performance/{session_id}
```

Each node log includes:

- session ID
- node name
- success or failure
- duration
- approximate input size
- approximate output size
- error message when applicable

This changed debugging from guesswork into stage-by-stage inspection.

## Final Phase 4 Flow

```text
1. Upload audio
2. Optionally upload PDF
3. Save temporary files
4. Run PDF OCR if PDF exists
5. Initialize graph state with audio path and OCR result
6. Transcribe audio with faster-whisper
7. Diarize speakers with SpeechBrain or fallback
8. Filter clinically relevant transcript content
9. Cross-check transcript values with OCR values
10. Extract clinical entities
11. Merge OCR-only lab values
12. Retrieve clinical guidelines
13. Generate SOAP note
14. Generate ICD-10 suggestions
15. Run QA guardrail
16. Run safety guardrail
17. Route to urgent safety, low confidence, or standard approval
18. Persist SOAP, labs, guidelines, provenance, QA, and safety artifacts
19. Return physician-review response
```

## What Phase 4 Achieved

By the end of Phase 4, MedScribe could:

- process audio consultations and PDF lab reports together
- extract objective labs from reports
- preserve source and verification metadata
- merge OCR-derived facts into entity extraction
- generate SOAP notes with report-aware objective findings
- support ICD-10, QA, safety, and review routing on richer context
- tolerate malformed JSON, schema drift, null fields, and missing sections
- keep the pipeline observable through per-node logs

The engineering lesson is simple but important: Phase 4 was not just a feature addition. It was the point where MedScribe became an integration-heavy clinical pipeline, and the reliability work at the boundaries became as important as the model prompts.
