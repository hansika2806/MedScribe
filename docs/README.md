# MedScribe Documentation Index

Use this index to choose the right document quickly.

## Phase 4 - PDF OCR and Clinical Intelligence

Start here if you are studying the latest multi-modal implementation:

- `PHASE4_IMPLEMENTATION.md` - Main implementation summary for PDF upload, OCR extraction, multi-source clinical fusion, SOAP, ICD, QA, safety, and persistence.
- `PHASE4_DATA_FLOW.md` - Step-by-step data movement from upload to OCR to graph state to SOAP and persisted lab values.
- `PHASE4_SCHEMA_AND_FALLBACKS.md` - The most important production lessons: schema drift, malformed JSON, source normalization, null handling, and conservative fallbacks.
- `PHASE4_TESTING_AND_DEBUGGING.md` - How to run Phase 4 tests and debug OCR, API, token, diarization, and validation failures.

Recommended reading order:

```text
PHASE4_IMPLEMENTATION.md
PHASE4_DATA_FLOW.md
PHASE4_SCHEMA_AND_FALLBACKS.md
PHASE4_TESTING_AND_DEBUGGING.md
```

## Earlier Phase Docs

- `PHASE1_PLAN.md` - Initial MVP plan.
- `PHASE2_COMPLETE.md` - Phase 2 completion notes.
- `PHASE2_FINAL_SUMMARY.md` - Phase 2 final implementation summary.
- `PHASE2_FINAL_FIXES.md` - Phase 2 final fixes.
- `PHASE2_TEST_SUITE.md` - Phase 2 tests.
- `PHASE3_PLAN.md` - Physician review workflow plan.

## General Docs

- `SETUP.md` - Project setup.
- `TESTING.md` - General testing guide, with Phase 4 pointers.
- `WORKFLOW.md` - Full conceptual workflow.
- `DEBUGGING_GUIDE.md` - General debugging notes.

## Bugfix Notes

- `BUGFIX_DATA_FLOW.md`
- `BUGFIX_DIARIZATION.md`
- `BUGFIX_PHASE2_PIPELINE.md`
