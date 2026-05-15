# Phase 4 Schema Hardening and Fallbacks

Phase 4 exposed the biggest reliability problem in multi-modal AI systems: most failures happen at interfaces. OCR, LLMs, Pydantic schemas, and clinical nodes can all be individually reasonable, but the pipeline still fails if one component returns a slightly different shape.

This document explains the hardening added in Phase 4 and the patterns to keep using.

## Why Hardening Was Needed

The system began receiving data from multiple probabilistic sources:

- Whisper transcription
- speaker diarization
- PaddleOCR
- regex table extraction
- LLM relevance filtering
- LLM entity extraction
- LLM SOAP generation
- guideline retrieval
- ICD lookup

Each source can produce partial, noisy, missing, or differently shaped output. Strict validation is still important, but Phase 4 showed that validation must happen after normalization, not before it.

## Failure Class 1: Source Label Drift

### Symptom

The pipeline expected:

```json
"source": "ocr_only"
```

OCR returned:

```json
"source": "ocr"
```

### Risk

Pydantic validation fails, causing a 500 error even though the extracted clinical value is usable.

### Fix

Normalize source labels at graph boundaries:

```python
if item.get("source") == "ocr":
    item["source"] = "ocr_only"
```

### Rule

Raw tool output can use tool-native labels. Pipeline schemas should use canonical labels.

## Failure Class 2: Invalid or Wrapped JSON

### Symptom

The LLM returned JSON surrounded by explanations, Markdown fences, or trailing text, causing:

```text
JSON parse error: Extra data
```

### Fix

Nodes now extract the first valid JSON object from the response. They support:

- fenced JSON blocks
- text before JSON
- text after JSON
- raw JSON object inside a larger response

### Rule

Never assume an LLM returns clean JSON just because the prompt asks for it. Always parse defensively.

## Failure Class 3: Shape Drift

### Symptom

The filter expected:

```json
{
  "filtered_utterances": []
}
```

The model returned variants such as:

```json
{
  "results": []
}
```

or:

```json
{
  "filtered_transcript": {
    "filtered_utterances": []
  }
}
```

### Fix

`filter.py` accepts common aliases:

```text
filtered_transcript
utterances
results
items
```

and normalizes them to:

```text
filtered_utterances
```

### Rule

Schema aliases should be accepted only at boundaries. Internal state should remain canonical.

## Failure Class 4: Over-Filtering

### Symptom

The filter excluded too much transcript content. Downstream extraction then failed because there was no clinical material.

### Fix

If fewer than two utterances are included, the filter falls back to including all utterances with conservative mapping.

### Why This Is Clinically Safer

For a physician-review pipeline, losing clinical context is worse than passing extra context forward. Extra context can be reviewed; missing context can silently weaken the note.

### Rule

Fallbacks should preserve information and lower confidence, not silently discard information.

## Failure Class 5: Empty Upstream Output Cascades

### Symptom

One node failed, then downstream nodes emitted:

```text
No filtered transcript available
No extracted entities
No SOAP note found
```

### Fix

Nodes now degrade more predictably:

- filter can build a deterministic fallback payload
- extractor can return empty but valid entity groups
- SOAP can generate fallback sections for missing model sections
- routing still directs physician review when confidence or QA fails

### Rule

Every node should either produce a valid minimal output or set a clear error. Avoid ambiguous half-state.

## Failure Class 6: OCR Entities Without Utterances

### Symptom

SOAP validation failed:

```text
utterance: null
Input should be a valid string
```

### Root Cause

OCR values do not naturally have a spoken utterance, but SOAP provenance expected one.

### Fix

For OCR-derived entities with no utterance:

```text
OCR extracted value: HbA1c 8.2
```

is used as the provenance utterance.

### Rule

Do not force document-derived data to pretend it came from speech. Give it a source-specific provenance string.

## Failure Class 7: Confidence and Null Normalization

### Symptoms

The model sometimes returned:

- confidence as a string
- confidence outside `0.0` to `1.0`
- null dosage
- null frequency
- null vital values
- missing age group

### Fixes

Phase 4 added normalizers that:

- coerce confidence to float
- clamp confidence between `0.0` and `1.0`
- replace medication nulls with `"unknown"`
- remove null vitals
- default missing age group to `"adult"`

### Rule

Normalize non-clinical structural defects. Do not invent clinical facts.

## Failure Class 8: Token Limit Pressure

### Symptom

SOAP generation exceeded the Groq request limit:

```text
Error 413
Request too large
```

### Root Cause

The prompt grew to include transcript context, extracted entities, OCR values, guideline snippets, provenance instructions, and output schema.

### Fix

SOAP prompt construction now:

- serializes JSON compactly
- limits entity list sizes
- limits guideline count
- shortens guideline excerpts
- uses `llama-3.3-70b-versatile`
- caps output with `LLM_MAX_TOKENS=2048`

### Rule

For clinical reasoning, reduce prompt waste before reducing model quality.

## Fallback Philosophy

Phase 4 uses conservative fallbacks:

| Situation | Preferred fallback |
| --- | --- |
| LLM JSON is wrapped in text | Extract first valid JSON object. |
| Filter schema is renamed | Normalize alias to canonical field. |
| Filter excludes too much | Pass more transcript forward with lower certainty. |
| OCR value lacks utterance | Use OCR-specific provenance text. |
| SOAP section missing | Create review-required fallback section. |
| Confidence malformed | Coerce and clamp. |
| Lab value source mismatch | Normalize to canonical source. |

The pattern is:

```text
normalize -> validate -> continue with traceability -> route to review if uncertain
```

not:

```text
trust raw model output -> validate immediately -> crash
```

## Boundary Checklist

Use this checklist whenever adding a new node, model prompt, or data source:

- Does the output have one canonical internal shape?
- Are common aliases normalized before validation?
- Are nulls handled without inventing clinical facts?
- Does every clinical claim keep source metadata?
- Can the pipeline continue safely if this node returns partial output?
- Is uncertainty visible to QA or physician review?
- Are prompt inputs bounded?
- Is the node visible in performance logs?

## Practical Debugging Order

When Phase 4 breaks, check in this order:

1. Did the API receive the PDF?
2. Did `ocr_result.status` equal `success`, `failed`, or `no_pdf`?
3. Did `test_report_values` contain the expected labs?
4. Did the filter normalize `source` to `ocr_only`?
5. Did the extractor merge OCR labs into `lab_values`?
6. Did SOAP objective include those values?
7. Did QA flag missing provenance?
8. Did safety or confidence routing change the final review type?
9. Did `/performance/{session_id}` show the slow or failed node?

## Main Lesson

Phase 4 made one thing obvious: prompts are not the architecture. The architecture is the set of contracts, normalizers, validators, fallbacks, and logs that keep imperfect AI outputs usable under clinical review.
