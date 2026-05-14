# Diarization Authentication Bug - Fix Documentation

## Problem
pyannote.audio speaker diarization failing with authentication error:
```
hf_hub_download() got an unexpected keyword argument 'use_auth_token'
```

## Root Cause
Version incompatibility between `huggingface_hub` and `pyannote.audio`:
- `pyannote.audio==3.1.1` internally uses deprecated `use_auth_token` parameter
- `huggingface_hub>=0.20.0` removed support for `use_auth_token` (replaced with `token`)
- When pyannote tries to download models, it calls `hf_hub_download(use_auth_token=...)` which fails

## Solution Attempts

### Attempt 1: Change parameter name ❌
Changed `use_auth_token` to `token` in diarization.py
**Result:** Failed - pyannote.audio 3.1.1 doesn't support `token` parameter

### Attempt 2: Use huggingface_hub.login() ❌
Called `login(token=settings.hf_token)` before loading pipeline
**Result:** Failed - pyannote internally still uses `use_auth_token` when calling `hf_hub_download()`

### Attempt 3: Set environment variables ❌
Set HF_TOKEN as environment variable before loading pipeline
**Result:** Failed - newer huggingface_hub doesn't check environment for deprecated parameter

### Attempt 4: Downgrade huggingface_hub ✅ (FINAL SOLUTION)
Pinned `huggingface_hub==0.19.4` - the last version that supports `use_auth_token`

**Why this works:**
- `huggingface_hub==0.19.4` still supports the deprecated `use_auth_token` parameter
- `pyannote.audio==3.1.1` can successfully call `hf_hub_download(use_auth_token=...)`
- Environment variables are still set for additional compatibility

## Files Modified
1. `backend/requirements.txt` - Pinned `huggingface_hub==0.19.4`
2. `backend/tools/diarization.py` - Environment variable setup (kept for compatibility)

## Installation
```bash
pip install huggingface_hub==0.19.4
```

## Testing
Restart server and test:
```bash
python backend/main.py
python tests/test_api.py
```

Expected output:
```
INFO: Setting HuggingFace token in environment...
INFO: ✅ HuggingFace token configured
INFO: ✅ Diarization model loaded successfully
INFO: Diarization complete. X utterances identified
```

## Long-term Solution
When `pyannote.audio` releases a version compatible with `huggingface_hub>=0.20.0`, upgrade both:
- Monitor: https://github.com/pyannote/pyannote-audio/issues
- Upgrade when pyannote.audio 3.2+ is released with `token` parameter support