# Phase 5 Implementation - Authentication, Polish, and Final Fixes

## Purpose

Phase 5 turned MedScribe from an open local prototype into a physician-aware review application. The goal was not production identity management yet. The goal was to make the Phase 1-4 pipeline usable in a realistic demo flow:

1. A physician logs in.
2. The frontend stores a short-lived session token.
3. Protected backend endpoints require that token.
4. Every consultation and approval is linked to the logged-in physician.
5. The UI shows the physician identity, handles expired sessions, and has a polished approval completion flow.

Production deployment, real physician database management, HTTPS, and cloud hosting remain Phase 6 work.

---

## What Phase 5 Added

### Backend

Created:

```text
backend/auth/
  __init__.py
  models.py
  service.py
  dependency.py
  router.py
```

Modified:

```text
backend/requirements.txt
backend/main.py
backend/api/routes.py
backend/database/models.py
backend/database/connection.py
backend/database/repository.py
backend/models/schemas.py
backend/tools/diarization.py
```

Backend capabilities added:

- JWT authentication with `python-jose`.
- Password verification with `passlib[bcrypt]`.
- Three hardcoded physician demo accounts.
- Bearer-token dependency for protected routes.
- Auth routes under `/auth`.
- Consultation creation linked to `physician_username`.
- Approval linked to both `physician_username` and `physician_name`.
- SQLite migration for existing databases.
- `approvals` table.
- FFmpeg automatic PATH setup at backend startup.
- Speechbrain local model storage fallback for Windows symlink issues.
- CORS support for auth headers.

### Frontend

Created:

```text
frontend/src/api/auth.js
frontend/src/components/LoginScreen.jsx
frontend/src/components/NavBar.jsx
frontend/src/components/ApprovalSuccessScreen.jsx
```

Modified:

```text
frontend/src/api/client.js
frontend/src/App.jsx
frontend/src/components/UploadScreen.jsx
frontend/src/components/ProcessingScreen.jsx
frontend/src/components/SOAPReview.jsx
frontend/src/components/ApproveButton.jsx
frontend/src/components/ErrorScreen.jsx
frontend/src/components/SafetyFlagsPanel.jsx
frontend/src/components/QAFlagsPanel.jsx
frontend/src/components/ProvenancePanel.jsx
frontend/src/components/GuidelineCitations.jsx
```

Frontend capabilities added:

- Login screen.
- Session token storage in `sessionStorage`.
- Physician information storage in `sessionStorage`.
- Authorization headers on API calls.
- Automatic logout on `401`.
- Shared navigation bar on all non-login screens.
- Physician identity displayed during review.
- File size and processing estimate after audio selection.
- More prominent elapsed time and progress bar.
- Full approval success screen.
- Read-only view after approval.
- Mobile layout improvements.
- Better empty states.
- Better human-readable error messages.

### Tests and Docs

Created:

```text
tests/test_phase5.py
docs/DEVELOPMENT_JOURNEY.md
docs/ARCHITECTURE_QUICK_REFERENCE.md
docs/TROUBLESHOOTING.md
docs/PHASE5_IMPLEMENTATION.md
```

Modified:

```text
README.md
```

---

## Authentication Design

### Why JWT

JWT was chosen because it is simple, stateless, and works naturally with FastAPI dependencies. The backend does not need to store sessions in SQLite. The frontend keeps the token for the current browser session only.

### Why Hardcoded Physicians

Phase 5 is still a local prototype/demo phase. A real user table, password reset flow, roles, account lockout, and audit-grade identity management would add too much complexity for this phase. The hardcoded accounts make it easy to demo identity-aware workflows while leaving the Phase 6 migration path clear.

### Demo Accounts

| Username | Password | Name | Department |
|---|---|---|---|
| dr.sharma | medscribe123 | Dr. Priya Sharma | General Medicine |
| dr.kumar | medscribe123 | Dr. Rahul Kumar | Cardiology |
| dr.patel | medscribe123 | Dr. Anjali Patel | Endocrinology |

### Token Settings

```python
SECRET_KEY = "medscribe-secret-key-2026-phase5"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 8
```

The token stores the username as `sub`. On every protected request, the backend decodes the token, checks that the username still exists in the hardcoded physician dictionary, and returns the physician profile.

### Auth API

#### POST `/auth/login`

Request:

```json
{
  "username": "dr.sharma",
  "password": "medscribe123"
}
```

Response:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "physician_name": "Dr. Priya Sharma",
  "username": "dr.sharma"
}
```

Invalid credentials return `401`.

#### GET `/auth/me`

Requires:

```text
Authorization: Bearer <token>
```

Response:

```json
{
  "username": "dr.sharma",
  "physician_name": "Dr. Priya Sharma",
  "department": "General Medicine"
}
```

Invalid or expired token returns `401`.

#### GET `/auth/logout`

Returns:

```json
{
  "status": "logged_out"
}
```

Logout is client-side only. The frontend clears `sessionStorage`.

---

## Protected Routes

The following routes require a valid bearer token:

```text
POST /consultation
GET /consultation/{session_id}
POST /consultation/{session_id}/approve
GET /metrics
GET /auth/me
```

The following routes remain public:

```text
GET /health
POST /auth/login
GET /auth/logout
```

Some helper endpoints remain available for the local workflow:

```text
GET /consultation/{session_id}/status
POST /consultation/{session_id}/labs
POST /consultation/{session_id}/retry
GET /performance/{session_id}
```

The main security boundary for Phase 5 is the consultation creation, consultation retrieval, approval, and metrics routes.

---

## Backend Auth Flow

```text
Login request
  |
  v
authenticate_physician(username, password)
  |
  |-- username missing -> 401
  |-- password mismatch -> 401
  |
  v
create_access_token({"sub": username})
  |
  v
return JWT + physician name
```

Protected request:

```text
Incoming request
  |
  v
HTTPBearer extracts token
  |
  v
verify_token(token)
  |
  |-- invalid signature -> 401
  |-- expired token -> 401
  |-- unknown username -> 401
  |
  v
current_physician dict injected into route
```

The key file is:

```text
backend/auth/dependency.py
```

It defines:

```python
async def get_current_physician(...)
```

This dependency is attached to protected FastAPI endpoints.

---

## Database Changes

### consultations Table

Added:

```sql
physician_username TEXT DEFAULT 'unknown'
```

Why: every generated consultation should be traceable to the physician who created it.

### approvals Table

Added:

```sql
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    physician_username TEXT,
    physician_name TEXT,
    approved_at TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES consultations(id)
)
```

Why: approval is clinically important and should be stored as a separate event. Even though this is not production-grade audit logging yet, it creates the right shape for Phase 6.

### Migration Strategy

Existing local SQLite databases already had a `consultations` table. `CREATE TABLE IF NOT EXISTS` would not add new columns to an existing table, so Phase 5 added a migration list:

```python
MIGRATION_STATEMENTS = [
    "ALTER TABLE consultations ADD COLUMN physician_username TEXT DEFAULT 'unknown'",
]
```

`backend/database/connection.py` runs these migrations during startup and safely ignores the duplicate-column error if the migration already ran.

Fallback behavior:

- Old rows get `physician_username = 'unknown'`.
- New rows get the logged-in username.
- If some old data is viewed, the app does not crash because the field is optional in the response model.

---

## Approval Flow

Before Phase 5, approval mostly changed the SOAP note approval flag. Phase 5 stores physician identity and returns a richer confirmation.

Request:

```text
POST /consultation/{session_id}/approve
Authorization: Bearer <token>
```

Response:

```json
{
  "status": "approved",
  "session_id": "...",
  "approved_at": "2026-05-15T10:30:00",
  "approved_by": "Dr. Priya Sharma",
  "physician_username": "dr.sharma"
}
```

Backend persistence:

- `soap_notes.approved = 1`
- `soap_notes.approved_at = approved_at`
- `consultations.physician_username = token username`
- new row inserted into `approvals`

Frontend behavior:

1. User clicks Approve.
2. `ApproveButton.jsx` calls `approveConsultation`.
3. Backend returns approval confirmation.
4. `SOAPReview.jsx` calls `onApproved`.
5. `App.jsx` moves to `success` screen.
6. `ApprovalSuccessScreen.jsx` shows session ID, physician, timestamp, review type, and confidence.

Fallback behavior:

- If approval fails, the sticky approval bar shows the backend error.
- If already approved, the note opens in read-only mode and the approval button is hidden.

---

## Frontend State Machine

Phase 5 added `login` and `success` to the existing state machine.

```text
App starts
  |
  v
isLoggedIn()?
  |-- no  -> login
  |-- yes -> upload

login
  -> upload
  -> processing
  -> review
  -> success

processing
  -> review on success
  -> error on failure

error
  -> retry
  -> upload new

success
  -> start new consultation
  -> view approved note
```

Stored browser values:

```text
medscribe_token
medscribe_physician
medscribe_session
medscribe_screen
```

`medscribe_token` and `medscribe_physician` are created after login. `medscribe_session` and `medscribe_screen` preserve review state during refresh.

### Why sessionStorage

`sessionStorage` was chosen over `localStorage` because the demo session should disappear when the browser tab/session ends. This is safer for a medical app prototype.

Fallback behavior:

- If `medscribe_physician` cannot be parsed, frontend returns `null` and uses generic labels.
- If token is missing, `isLoggedIn()` returns false and the app shows LoginScreen.
- If any API call returns `401`, the frontend clears session and redirects to login.

---

## UI Polish Details

### NavBar

`NavBar.jsx` appears on every screen except login.

It shows:

- MedScribe logo/name.
- Physician name.
- Department.
- Logout button.

Mobile behavior:

- Nav stacks vertically.
- Logout becomes full width.
- Physician text truncates instead of overflowing.

### Login Screen

`LoginScreen.jsx` includes:

- Centered card.
- MedScribe logo/title.
- Clinical Documentation AI subtitle.
- Username field.
- Password field.
- Login button.
- Loading state.
- Error message.
- Demo credentials.

### Upload Screen

After audio selection, it shows:

```text
Audio file: consultation.wav (4.1 MB)
Estimated processing time: 45-60 seconds
```

Fallback estimate:

- Files larger than 8 MB show `60-90 seconds`.
- Smaller files show `45-60 seconds`.

### Processing Screen

Added:

- Prominent elapsed time.
- Progress bar filling over 90 seconds.
- Existing 11-stage status list preserved.

Fallback behavior:

- Status polling failures do not crash the screen.
- If backend reports `failed`, it moves to the error screen.

### Error Screen

Human-readable mappings:

| Backend signal | User message |
|---|---|
| `Rate limit reached` or `429` | AI service is temporarily busy. Please wait a few minutes and try again. |
| `No extracted entities` | Could not extract clinical information from the audio. Please check audio quality and ensure the consultation was clearly recorded. |
| `Groq API error` or `500` | Processing service temporarily unavailable. Please try again in a moment. |
| `Network Error` or no response | Cannot connect to MedScribe server. Please check your connection. |
| `401` or `Unauthorized` | Your session has expired. Please log in again. |

Fallback behavior:

- Unknown errors use a generic message.
- Session-expiry errors trigger logout shortly after display.

### Empty States

Added:

- Provenance: `No provenance records available for this section`
- Guidelines: `No guidelines retrieved for this section`
- Safety: `No safety risks detected`
- QA: `All quality checks passed`

### Mobile Fixes

Key mobile changes:

- Nav stacks.
- Tables scroll horizontally.
- Approval button is full width on mobile.
- Review header uses `break-all` for long session IDs.
- Cards and panels stay within the 375px viewport.

---

## Speechbrain Diarization Fix

### Problem

Speechbrain and HuggingFace model cache behavior on Windows can try to create symlinks. Windows may reject that with:

```text
WinError 1314: A required privilege is not held by the client
```

### Fix Added

In `backend/tools/diarization.py`:

```python
os.environ["SPEECHBRAIN_FETCH_LOCAL_STORAGE"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
```

Model load now uses:

```python
EncoderClassifier.from_hparams(
    source="speechbrain/spkrec-ecapa-voxceleb",
    savedir="data/models/speechbrain",
    run_opts={"device": "cpu"},
)
```

Why: `savedir="data/models/speechbrain"` keeps model artifacts inside the project folder and avoids relying on the global HuggingFace cache.

Fallback behavior:

- If Speechbrain imports fail, fallback diarization is used.
- If model loading fails, fallback diarization is used.
- If embedding extraction or clustering fails, fallback labels are used.
- Logs clearly say whether Speechbrain or fallback alternating diarization was selected.

Current expected logs can include harmless warnings:

```text
torchaudio backend switched to soundfile
torchaudio.set_audio_backend has been deprecated
Speechbrain available for real diarization via speechbrain.pretrained
```

These warnings are not fatal.

---

## FFmpeg PATH Fix

### Problem

Audio processing needed FFmpeg, but Windows did not always have FFmpeg in PATH.

### Fix Added

`backend/main.py` now calls `setup_ffmpeg()` before the app initializes. It checks:

```text
C:\Users\<user>\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin
```

If found, it prepends that folder to `PATH`.

Fallback behavior:

- If the path exists, backend logs that FFmpeg was added.
- If not found, backend logs a warning but still starts.
- Audio processing may fail later if FFmpeg is truly unavailable.

---

## CORS Changes

Phase 5 requires the frontend to send:

```text
Authorization: Bearer <token>
```

So CORS now allows:

```python
allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
],
allow_credentials=True,
allow_methods=["*"],
allow_headers=["*", "Authorization"],
```

Why both origins: Vite/browser testing sometimes uses `localhost`, sometimes `127.0.0.1`. Both must be accepted.

---

## Phase 5 Test Script

Created:

```text
tests/test_phase5.py
```

It tests:

1. Login with valid credentials.
2. `/auth/me` with token.
3. Login with wrong password returns `401`.
4. `/consultation` without token returns `401`.
5. `/consultation` with token processes normally.
6. Approval returns physician name.
7. Fake token is rejected on protected endpoints.

Run sequence:

```bat
cd C:\Users\nagah\Projects\MedScribe
venv\Scripts\activate
python -m backend.main
```

In another terminal:

```bat
cd C:\Users\nagah\Projects\MedScribe
venv\Scripts\activate
python tests\test_phase5.py
```

Expected output:

```text
PASS: Backend health reachable
PASS: Auth login returns token
PASS: Auth me returns physician info
PASS: Wrong password returns 401
PASS: Protected consultation rejects missing token
PASS: Protected consultation with token processes normally
PASS: Approval stores physician name
PASS: Fake token rejected on ...
```

Fallback behavior:

- If Groq rate limit is hit, auth tests can still pass but the full consultation test may fail.
- If that happens, switch to `LLM_MODEL=llama-3.1-8b-instant`, restart backend, and rerun.

---

## Setbacks Encountered During Phase 5

### Setback 1: passlib and bcrypt incompatibility

Error:

```text
passlib.handlers.bcrypt - WARNING - (trapped) error reading bcrypt version
AttributeError: module 'bcrypt' has no attribute '__about__'
ValueError: password cannot be longer than 72 bytes
```

Root cause:

`passlib==1.7.4` is not compatible with newer `bcrypt` package behavior. The newer package removed metadata that passlib expected, and startup failed when hashes were generated at import time.

Fix:

Pinned:

```text
bcrypt==4.0.1
```

in `backend/requirements.txt`, then installed:

```bat
pip install bcrypt==4.0.1
```

Why it worked:

`bcrypt==4.0.1` is compatible with `passlib==1.7.4`.

Prevention:

Keep both packages pinned together:

```text
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
```

### Setback 2: Frontend command run from wrong directory

Error:

```text
npm error enoent Could not read package.json
npm error path C:\Users\nagah\Projects\MedScribe\package.json
```

Root cause:

The React app lives in:

```text
C:\Users\nagah\Projects\MedScribe\frontend
```

but `npm run dev` was run from the project root.

Fix:

```bat
cd C:\Users\nagah\Projects\MedScribe\frontend
npm run dev
```

Prevention:

Always run backend commands from project root and frontend commands from the `frontend` folder.

### Setback 3: PowerShell curl warning

Behavior:

PowerShell aliases `curl` to `Invoke-WebRequest`, which can show a script parsing warning.

Fix:

Use:

```bat
curl.exe http://localhost:8000/health
```

or:

```bat
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
```

### Setback 4: Python launcher confusion

Observed during automated verification:

```text
Unable to create process using ... Python311\python.exe
No installed Python found
```

Root cause:

The local virtual environment or Python launcher was pointing at a missing Python install during one verification attempt.

Actual resolution:

The user activated the existing venv successfully and could run:

```bat
python -m backend.main
```

Prevention:

If this happens again, recreate the venv after reinstalling Python 3.11:

```bat
cd C:\Users\nagah\Projects\MedScribe
Remove-Item -Recurse -Force venv
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
```

### Setback 5: esbuild sandbox access during build

Error:

```text
Cannot read directory "../../..": Access is denied.
Could not resolve vite.config.js
```

Root cause:

The local build toolchain uses esbuild native execution, which can be blocked by sandbox restrictions.

Fix:

Run `npm run build` outside the restricted sandbox. The build completed successfully:

```text
vite build
99 modules transformed
built successfully
```

Prevention:

For local user testing, run from a normal PowerShell terminal:

```bat
cd C:\Users\nagah\Projects\MedScribe\frontend
npm run build
```

### Setback 6: Speechbrain warnings on startup

Warnings:

```text
sox_io is not supported on Windows
torchaudio.set_audio_backend has been deprecated
```

Root cause:

Speechbrain/torchaudio uses backend selection logic that emits warnings on Windows.

Fix:

No code fix required. These are warnings, not fatal errors.

Prevention:

Only investigate if diarization fails and the app logs that it fell back.

---

## Fallbacks Added or Preserved

### Authentication fallback

- Missing token returns `401`.
- Invalid token returns `401`.
- Expired token returns `401`.
- Frontend clears session and returns to login.

### Physician data fallback

- Existing DB rows use `physician_username = 'unknown'`.
- Frontend shows generic physician labels if stored physician data is missing.

### Diarization fallback

- Speechbrain available and model loads: use Speechbrain.
- Speechbrain unavailable or fails: use fallback alternating Doctor/Patient diarization.
- Clustering fails: use alternating labels with lower confidence.

### FFmpeg fallback

- Known WinGet path found: prepend to PATH.
- Path not found: log warning and continue startup.

### OCR fallback

Preserved from Phase 4:

- No PDF uploaded: pipeline sets `ocr_method = "no_pdf"`.
- OCR fails: pipeline can continue with transcript-derived information and manual lab entry.

### LLM/API fallback

Preserved:

- Groq 429 is mapped to a clear busy-service message.
- Smaller model can be used for testing.

### UI fallback

- No provenance records: show empty state.
- No guidelines: show empty state.
- No safety flags: show green success state.
- No QA flags: show green success state.
- Network failure: show connection message.
- Unknown error: show generic retry message.

---

## Current Phase 5 Status

Confirmed working:

- Backend starts.
- `/health` returns `0.5.0-phase5`.
- Login works.
- Frontend works when started from `frontend`.
- bcrypt/passlib crash resolved by pinning `bcrypt==4.0.1`.
- Speechbrain warnings do not block backend startup.

Still prototype-level:

- Users are hardcoded.
- Secret key is hardcoded.
- Tokens cannot be revoked server-side.
- Approval table is not a full audit log.
- No HTTPS.
- No role-based authorization.

These are expected and intentionally deferred to Phase 6.

---

## How to Run Phase 5

Terminal 1 - backend:

```bat
cd C:\Users\nagah\Projects\MedScribe
venv\Scripts\activate
python -m backend.main
```

Health check:

```bat
curl.exe http://localhost:8000/health
```

Terminal 2 - frontend:

```bat
cd C:\Users\nagah\Projects\MedScribe\frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

Login:

```text
dr.sharma / medscribe123
```

Run test script:

```bat
cd C:\Users\nagah\Projects\MedScribe
venv\Scripts\activate
python tests\test_phase5.py
```

---

## Phase 6 Migration Notes

Recommended next steps:

1. Move physicians into a database table.
2. Store password hashes generated once, not at import time.
3. Move `SECRET_KEY` to `.env`.
4. Add token revocation or refresh-token strategy.
5. Add roles such as physician, admin, reviewer.
6. Add audit-grade approval events.
7. Add HTTPS.
8. Add production CORS origins only.
9. Add database migrations with Alembic.
10. Replace prototype sessionStorage auth with a hardened production pattern.
