# MedScribe Troubleshooting

## ModuleNotFoundError: fastapi
Root cause: the backend was run outside the virtual environment or from the wrong import root.

Fix:
```bat
cd C:\Users\nagah\Projects\MedScribe
venv\Scripts\activate
pip install -r backend\requirements.txt
python -m backend.main
```

Prevention: always run the backend as a module from the project root.

## use_auth_token Deprecated
Root cause: newer HuggingFace Hub versions removed or changed older auth parameters used by pyannote.

Fix attempted: changed calls to `token=`, tried environment variables, and tested hub login.

Prevention: pin compatible pyannote and HuggingFace Hub versions, or avoid pyannote on this Windows prototype.

## Pipeline.from_pretrained Token Parameter
Root cause: pyannote and HuggingFace Hub expected different parameter names across versions.

Fix attempted: replaced `use_auth_token` with `token`, then tested direct environment-token loading.

Prevention: keep model-loading code version-specific and document accepted model gates.

## Hub Connection Error pyannote
Root cause: model downloads from HuggingFace failed after authentication/version changes.

Fix: moved away from pyannote for this prototype and kept fallback diarization available.

Prevention: cache models ahead of demos, or deploy on a Linux host with stable model access.

## Speechbrain WinError 1314
Exact message: `WinError 1314: A required privilege is not held by the client`.

Root cause: HuggingFace/Speechbrain cache tried to create symlinks on Windows without elevated privileges.

Fix: set `SPEECHBRAIN_FETCH_LOCAL_STORAGE=1`, set `HF_HUB_DISABLE_SYMLINKS_WARNING=1`, and load the model with `savedir="data/models/speechbrain"` plus CPU run options. If model loading still fails, fallback alternating diarization continues.

Prevention: use the project-local model directory, enable Windows Developer Mode, or deploy on Linux.

## llama-3.1-70b-versatile Decommissioned
Root cause: the configured Groq model name was retired.

Fix: change `.env` to `LLM_MODEL=llama-3.3-70b-versatile`.

Prevention: verify model names before demos.

## Groq 429 Rate Limit
Root cause: the free tier daily token limit was exhausted during heavy testing.

Fix: wait for reset or use `LLM_MODEL=llama-3.1-8b-instant` for test runs.

Prevention: use short audio for smoke tests and reserve 70B for demos.

## requirements.txt Empty
Root cause: the file existed before dependencies were populated.

Fix: add all backend dependencies and run `pip install -r backend\requirements.txt`.

Prevention: update requirements whenever adding imports.

## CORS Error on Status Polling
Root cause: frontend origins alternated between `localhost:5173` and `127.0.0.1:5173`.

Fix: allow both origins and include authorization headers in CORS.

Prevention: keep frontend URLs consistent during testing.

## Pydantic Validation Errors: uncertain_spans
Root cause: LLM output sometimes returned `None` or malformed values for optional SOAP fields.

Fix: add sanitization before model creation and default missing lists to empty lists.

Prevention: validate all LLM JSON before creating Pydantic models.

## Pydantic Validation Errors: medication None
Root cause: LLM output returned `None` where the schema expected strings.

Fix: make medication fields optional/defaulted and sanitize missing values.

Prevention: keep schemas tolerant at LLM boundaries and strict inside persistence.

## Clinical Filter Excluding All Utterances
Root cause: fallback diarization can assign speakers mechanically, making the filter too strict.

Fix: if fewer than two utterances are included, pass all utterances through.

Prevention: improve diarization and keep a defensive bypass.

## ffmpeg Not Found in PATH
Root cause: Windows sessions did not permanently include the WinGet FFmpeg path.

Fix: `backend/main.py` now adds the known WinGet FFmpeg `bin` directory to `PATH` on startup.

Prevention: keep the startup setup and verify the WinGet install path after FFmpeg upgrades.

## ChromaDB Telemetry Error
Exact message: `capture() takes 1 positional argument but 3 were given`.

Root cause: ChromaDB telemetry/version mismatch.

Fix: non-breaking warning; retrieval continues. Suppress telemetry if it becomes noisy.

Prevention: pin ChromaDB and telemetry dependencies together.

## npm Build esbuild Sandbox Error
Root cause: esbuild native binary execution can be blocked by sandbox restrictions.

Fix: rerun `npm run build` with approved sandbox escalation when needed.

Prevention: keep `node_modules` installed locally and use approved build commands for this workspace.

## passlib bcrypt Version Crash
Exact messages:

```text
passlib.handlers.bcrypt - WARNING - (trapped) error reading bcrypt version
AttributeError: module 'bcrypt' has no attribute '__about__'
ValueError: password cannot be longer than 72 bytes
```

Root cause: `passlib==1.7.4` is incompatible with newer `bcrypt` package behavior.

Fix:

```bat
cd C:\Users\nagah\Projects\MedScribe
venv\Scripts\activate
pip install bcrypt==4.0.1
```

Prevention: keep these requirements pinned together:

```text
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
```

## npm run dev from Project Root
Exact message:

```text
npm error enoent Could not read package.json
npm error path C:\Users\nagah\Projects\MedScribe\package.json
```

Root cause: the frontend `package.json` is inside the `frontend` folder, not the project root.

Fix:

```bat
cd C:\Users\nagah\Projects\MedScribe\frontend
npm run dev
```

Prevention: run backend commands from the project root and frontend commands from `frontend`.

## PowerShell curl Security Warning
Root cause: in PowerShell, `curl` is often an alias for `Invoke-WebRequest`, which can warn about parsing page content.

Fix:

```bat
curl.exe http://localhost:8000/health
```

or:

```bat
Invoke-WebRequest http://localhost:8000/health -UseBasicParsing
```

Prevention: use `curl.exe` explicitly in PowerShell.
