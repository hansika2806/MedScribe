# Phase 4 Data Flow - Audio, PDF, OCR, and Clinical Context

This document explains how data moves through Phase 4. Use it when you need to understand where a lab value came from, why a value appears in SOAP, or which node is responsible for a malformed payload.

## High-Level Flow

```text
Frontend upload
    |
    v
POST /consultation
    |
    +-- audio_file -> data/temp/{session_id}.wav
    |
    +-- optional pdf_file -> data/temp/{session_id}.pdf
                          -> process_pdf()
                          -> ocr_result
                          -> test_report_values
    |
    v
PipelineState
    |
    v
LangGraph pipeline
    |
    v
ConsultationResponse + persisted session artifacts
```

## State Shape

The graph state is the contract between nodes. Phase 4 added PDF and OCR fields beside the existing transcript and clinical reasoning fields.

```python
{
    "audio_path": "...",
    "pdf_path": "...",
    "ocr_result": {
        "raw_text": "...",
        "lab_values": {},
        "page_count": 1,
        "source": "ocr",
        "status": "success"
    },
    "ocr_method": "paddleocr",
    "test_report_values": {},
    "transcript_raw": None,
    "transcript_diarized": None,
    "filtered_transcript": None,
    "extracted_entities": None,
    "retrieved_guidelines": [],
    "soap_note": None,
    "icd10_codes": [],
    "qa_result": {},
    "safety_result": {}
}
```

The main rule is: OCR is extracted before the graph starts, but it is consumed throughout the graph.

## Source Types

Phase 4 introduced stricter source tracking.

| Source | Meaning |
| --- | --- |
| `transcript` | Value came from consultation audio. |
| `ocr` | Raw OCR tool output before graph normalization. |
| `ocr_only` | Value came from the PDF report only. |
| `transcript_only` | Value was mentioned verbally but not confirmed by PDF. |
| `both` | Value was present in both transcript and OCR report. |
| `manual_physician_entry` | Value is entered later by a physician, supported by the broader review flow. |

The important implementation detail is that OCR starts as `ocr`, then clinical nodes normalize it to `ocr_only` where schemas require that exact value.

## Lab Value Lifecycle

Example lab value lifecycle:

```text
PDF table says: HbA1c 8.2
    |
    v
backend/tools/ocr.py
    |
    v
{
  "HbA1c": {
    "value": "8.2",
    "source": "ocr",
    "verified": true,
    "flag": null
  }
}
    |
    v
PipelineState.test_report_values
    |
    v
filter.py checks transcript against OCR values
    |
    v
extractor.py normalizes source to ocr_only and merges if omitted by LLM
    |
    v
SOAP objective section can mention HbA1c with provenance
    |
    v
routes.py persists lab values and returns them in the API response
```

## OCR Result Contract

Successful OCR returns:

```json
{
  "raw_text": "full extracted report text",
  "lab_values": {
    "HbA1c": {
      "value": "8.2",
      "source": "ocr",
      "verified": true,
      "flag": null
    }
  },
  "page_count": 1,
  "source": "ocr",
  "status": "success"
}
```

Failed OCR returns:

```json
{
  "raw_text": "",
  "lab_values": {},
  "page_count": 0,
  "source": "ocr",
  "status": "failed",
  "error": "..."
}
```

No PDF returns:

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

These three shapes allow the rest of the pipeline to behave predictably.

## Node Responsibilities

### API Route

`backend/api/routes.py` owns:

- accepting audio and optional PDF
- saving temporary files
- running OCR before pipeline invocation
- initializing `PipelineState`
- persisting final artifacts
- returning OCR fields in the response

Response fields added or made Phase 4 relevant:

```json
{
  "ocr_method": "paddleocr",
  "ocr_page_count": 1,
  "extracted_lab_values": {},
  "lab_values": []
}
```

### OCR Tool

`backend/tools/ocr.py` owns:

- PDF opening
- page rendering
- PaddleOCR extraction
- embedded-text fallback
- regex lab extraction
- verification metadata

It should not decide clinical meaning. It extracts facts from documents.

### Filter Node

`backend/pipeline/nodes/filter.py` owns:

- transcript relevance filtering
- SOAP-section mapping hints
- speaker uncertainty checks
- lab cross-verification
- filter response normalization
- conservative fallback if the model output is malformed or too restrictive

### Extractor Node

`backend/pipeline/nodes/extractor.py` owns:

- extracting symptoms, meds, vitals, labs, family history, and population tags
- normalizing missing fields
- removing null vital entries
- converting OCR source labels
- merging OCR labs if the model omits them

### SOAP Node

`backend/pipeline/nodes/soap.py` owns:

- assembling compact clinical context
- limiting prompt size
- generating SOAP sections
- normalizing SOAP schema drift
- creating fallback sections when needed
- ensuring OCR provenance has a non-null utterance

### RAG, ICD, QA, and Safety

These nodes consume the richer clinical context created upstream:

- RAG receives population and condition context.
- ICD consumes assessment diagnoses.
- QA validates SOAP completeness, confidence, provenance, and missing data.
- Safety checks medication, diagnosis, and dosage risks.

## Persistence Flow

After a successful run, `routes.py` persists:

- consultation session
- SOAP note
- ICD-10 diagnoses
- provenance records
- retrieved guidelines
- QA result
- safety result
- lab values

Lab values are gathered from extracted entities first, then OCR values are added if they were not already present.

## Reading a Phase 4 Response

When debugging an API response, read these fields in this order:

1. `status`: Did the pipeline complete?
2. `ocr_method`: Was the PDF path used?
3. `ocr_page_count`: Did the PDF open correctly?
4. `extracted_lab_values`: What OCR found directly.
5. `lab_values`: What was persisted/returned as structured clinical data.
6. `soap_note.objective`: Whether objective findings entered the note.
7. `qa_result.flags`: Whether missing provenance or low confidence was detected.
8. `safety_result.safety_flags`: Whether urgent review was triggered.
9. `review_type`: Which physician review path was selected.

## Mental Model

Phase 4 works best if you think of the PDF as a second clinical witness:

- The transcript captures symptoms, history, and physician decisions.
- OCR captures objective report evidence.
- The filter reconciles the two.
- The extractor turns them into structured facts.
- SOAP, ICD, QA, and safety consume the combined record.

The danger zone is not any one model call. The danger zone is every boundary where one shape becomes another shape.
