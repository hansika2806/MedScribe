# MedScribe Phase 3 Plan

Phase 3 turns the current Phase 2 backend into a physician-facing review workflow. The goal is not just to display a generated SOAP note. The goal is to support a safe review, correction, approval, and persistence loop where the note is not saved until the physician explicitly approves it.

## Scope

Phase 3 includes:

1. React frontend for consultation upload, processing progress, SOAP review, safety review, QA review, lab completion, and approval.
2. SQLite persistence for consultation sessions, SOAP notes, approvals, provenance records, guidelines, QA flags, safety flags, and pending lab values.
3. Backend API additions for session retrieval, progress/status polling, lab value updates, approval, retry, and stored note retrieval.
4. Browser-side session persistence so a refresh does not lose the current unapproved note.
5. Clear state-specific physician review views for `urgent_safety`, `low_confidence`, and `standard_approval`.

## User Experience Requirements

### Consultation Processing Screen

The pipeline can take 60-90 seconds, so the UI must never look frozen.

Show a processing view immediately after upload with:

- Session ID.
- Overall status: uploading, processing, completed, failed.
- Current pipeline node:
  - uploading audio
  - transcribing
  - diarizing speakers
  - filtering clinical content
  - extracting entities
  - retrieving guidelines
  - generating SOAP note
  - mapping ICD-10 codes
  - checking QA
  - checking safety
  - ready for physician review
- A visual progress indicator.
- A short, plain status message.

Backend implication: the API needs a status/progress source. If the processing remains synchronous initially, the frontend can show an estimated stepper. Preferred Phase 3 target is async session processing with persisted node status.

### Error State

If processing fails, the UI must show a clear error state instead of silently crashing.

Show:

- Human-readable error title.
- Error detail from API when available.
- Session ID if one exists.
- Retry button.
- Option to upload a different audio file.

Backend implication: pipeline errors should return structured error payloads and should be persisted against the session.

### Session Persistence On Refresh

If the physician refreshes before approval, the SOAP note must not disappear.

Minimum requirement:

- Store the active `session_id` and last completed response in browser storage.
- On page load, restore the current review screen if local data exists.

Preferred requirement:

- Store every session server-side in SQLite.
- On page load, call `GET /consultation/{session_id}` to restore the authoritative session state.

### SOAP Display

The SOAP note review screen must show all four sections:

- Subjective
- Objective
- Assessment
- Plan

Each section must show:

- Section content.
- Confidence score.
- Amber highlighting for uncertain spans.
- Collapsible provenance panel for each entity.

Uncertain spans should be visually tied to the relevant confidence/review reason. They should not be hidden only inside raw JSON.

### Provenance Panels

Every displayed entity should have a collapsible provenance panel showing:

- Claim.
- Source: transcript, OCR, or both.
- Speaker.
- Original utterance.
- Verified status.
- Entity confidence.

This should be available directly beside or under the claim, not only in a global debug dump.

### Diagnoses And ICD-10

In the Assessment section:

- Show each diagnosis as its own row or list item.
- Show ICD-10 code beside the diagnosis when available.
- Show `PENDING` or "manual coding required" clearly when lookup fails.

Backend implication: ICD-10 codes should be included as structured response data, not only appended into the assessment text.

### Plan And Guideline Citations

In the Plan section:

- Show plan items clearly.
- Show guideline citations alongside relevant plan items.
- Let the physician expand citation details where possible:
  - source
  - year
  - section
  - relevance score
  - excerpt

### Approval Flow

The note must not be saved as approved until the physician clicks Approve.

Approve button behavior:

- Disabled while required fields are missing.
- Disabled while urgent safety flags are unresolved or acknowledged, depending on final clinical policy.
- On click, send approval request to backend.
- Backend writes approval timestamp, physician identity when available, final SOAP note, full provenance, QA result, safety result, guidelines, and lab values to SQLite.

Backend implication: add an approval endpoint such as `POST /consultation/{session_id}/approve`.

### Pending Lab Values

The UI must support input fields for pending lab values.

Requirements:

- Show pending lab values in Objective or a dedicated "Labs" panel.
- Allow manual physician entry for lab name, value, unit, date, and optional note.
- Mark manually entered labs as source `manual_physician_entry`.
- Re-run or refresh SOAP/QA if lab changes affect the note.
- Persist entered labs before approval.

Schema implication: provenance currently allows `transcript`, `ocr`, and `both`. Phase 3 should add a manual-source model or extend source literals carefully.

## Review-Type-Specific Views

### urgent_safety

This must be visually prominent and hard to miss.

Show:

- Red urgent review banner.
- Safety flags panel with red flag cards.
- One card per `safety_flags` item.
- Each card should show:
  - check type: drug interaction, red flag diagnosis, dosage, or system error
  - detail
  - urgency
  - related medication/diagnosis if available
- SOAP note below the safety panel.
- Approval gated behind explicit acknowledgement or resolution policy.

This is more than a different page title. The specific safety risks must be visible.

### low_confidence

Show:

- Amber review banner.
- QA flags display.
- Confidence summary by SOAP section.
- Uncertain spans highlighted in the SOAP text.
- Suggested areas requiring physician review.

### standard_approval

Show:

- Neutral/success review banner.
- Normal SOAP review layout.
- Confidence scores and provenance still visible.
- Approve button still required.

## QA Flags Display

The UI must show which QA failure modes triggered, not just pass/fail.

Display the five QA categories:

1. Missing fields.
2. Population mismatch.
3. Low confidence.
4. Undocumented entities.
5. Provenance integrity.

For each triggered flag, show:

- Failure mode.
- Affected section.
- Detail.
- Severity or review priority if available.

Backend implication: preserve `qa_result.flags` as structured data and avoid reducing it to a boolean in frontend state.

## SQLite Storage Requirements

Create SQLite storage for:

- Consultations:
  - session ID
  - status
  - review type
  - timestamps
  - processing time
  - diarization method
  - error message
- SOAP notes:
  - session ID
  - subjective, objective, assessment, plan content
  - section confidence scores
  - final approved state
- Diagnoses and ICD-10:
  - diagnosis text
  - ICD-10 code
  - lookup description
  - pending/manual status
- Provenance records:
  - entity/claim
  - SOAP section
  - source
  - speaker
  - utterance
  - verified
  - confidence
- Retrieved guidelines:
  - source
  - year
  - section
  - relevance score
  - content/excerpt
- QA results:
  - overall confidence
  - section scores
  - flags
  - pass/fail
- Safety results:
  - safety pass/fail
  - flags
  - urgency
- Lab values:
  - lab name
  - value
  - unit
  - source
  - verified
  - flag
- Approvals:
  - approved timestamp
  - physician ID when available
  - final note snapshot

## API Requirements

Add or complete:

- `POST /consultation`
  - create session and start processing.
- `GET /consultation/{session_id}`
  - return full persisted session state.
- `GET /consultation/{session_id}/status`
  - return current node, status, error, and progress.
- `POST /consultation/{session_id}/labs`
  - add or update pending lab values.
- `POST /consultation/{session_id}/approve`
  - approve and persist final note.
- `POST /consultation/{session_id}/retry`
  - retry failed processing when possible.

## Frontend Acceptance Criteria

Phase 3 is complete when:

- A physician can upload consultation audio from the UI.
- The UI shows processing progress and current pipeline node.
- A failed run shows a useful error screen with retry.
- Refreshing the browser can restore the active session.
- The SOAP note displays all four sections with confidence scores.
- Uncertain spans are amber-highlighted.
- Entity provenance is available in collapsible panels.
- ICD-10 codes appear beside diagnoses.
- Guideline citations appear beside plan items.
- `urgent_safety` shows prominent red safety flag cards.
- `low_confidence` shows QA flags and uncertain areas.
- `standard_approval` still requires explicit physician approval.
- Pending lab values can be entered before approval.
- Clicking Approve persists the final SOAP note and full provenance in SQLite.

## Implementation Order

1. Add SQLite models/repository layer and session persistence.
2. Complete backend session retrieval and approval endpoints.
3. Add pipeline status/progress tracking.
4. Create React app shell with upload and processing screen.
5. Build SOAP review display with confidence and uncertain spans.
6. Build provenance, safety flags, QA flags, ICD-10, and citations panels.
7. Add pending lab value editing.
8. Add approval flow and refresh restoration.
9. Add frontend and backend tests for all review types.

