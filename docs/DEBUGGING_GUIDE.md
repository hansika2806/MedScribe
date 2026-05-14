# MedScribe Debugging Guide

## Current Issue: "No extracted entities available for SOAP generation"

### What This Error Means
The SOAP Generator (Node 11) is not receiving any extracted entities from the Clinical Extractor (Node 8). This means data is being lost somewhere in the pipeline between:
- Node 7: Clinical Relevance Filter
- Node 8: Clinical Extractor  
- Node 11: SOAP Generator

### Step-by-Step Debugging

#### Step 1: Check Server Logs

The test client only shows the final error. You need to check the **server logs** where you ran `python backend/main.py`.

Look for these log sections:
```
================================================================================
NODE 7: Clinical Relevance Filter
================================================================================
📝 Input: X diarized utterances
🤖 Calling LLM for clinical relevance filtering...
✅ LLM generated X characters
✅ Successfully parsed JSON response
✅ Filter complete:
   Total utterances: X
   Included: X
   Excluded: X
```

If you see ❌ errors in Node 7, that's where the problem is.

#### Step 2: Common Issues and Solutions

##### Issue 1: LLM Returns Non-JSON Response

**Symptom in logs:**
```
❌ Failed to parse JSON response
Error: Expecting value: line 1 column 1 (char 0)
```

**Cause:** Groq API returned text instead of JSON

**Solution:** The LLM prompt might need adjustment. Check if the system prompt is being sent correctly.

##### Issue 2: Empty Filtered Utterances

**Symptom in logs:**
```
✅ Filter complete:
   Included: 0
   Excluded: 16
```

**Cause:** Filter is excluding everything as non-clinical

**Solution:** The audio might not contain clinical content, or the filter is too aggressive.

##### Issue 3: Filter Succeeds But Extractor Fails

**Symptom in logs:**
```
NODE 7: ✅ Filter complete: 12 included
NODE 8: ❌ No filtered transcript available for extraction
State keys: ['audio_path', 'transcript_raw', 'transcript_diarized']
```

**Cause:** `filtered_transcript` not being added to state

**Solution:** Check if Node 7 is properly setting `state["filtered_transcript"]`

##### Issue 4: Extractor Returns Empty Entities

**Symptom in logs:**
```
NODE 8: ✅ Extraction complete:
   Symptoms: 0
   Medications: 0
   Vitals: 0
```

**Cause:** LLM extracted nothing from the filtered utterances

**Solution:** Check the filtered utterances being passed to the extractor

#### Step 3: Enable Debug Logging

Add this to the top of `backend/main.py`:

```python
import logging
logging.basicConfig(
    level=logging.DEBUG,  # Change from INFO to DEBUG
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

This will show:
- Full LLM prompts being sent
- Complete LLM responses
- Detailed state transitions

#### Step 4: Check Test Audio Quality

The test audio file might be the issue:

```bash
# Check audio file exists and has content
ls -lh tests/test_consultation.wav

# Should show file size > 1MB
```

If the file is too small or corrupted, regenerate it:

```bash
python tests/generate_test_audio.py
```

#### Step 5: Test Individual Components

Run the component tests to isolate the issue:

```bash
python tests/test_phase1.py
```

This tests each component with mock data. If these pass but the full pipeline fails, the issue is in data flow between nodes.

### Diagnostic Commands

#### Check if models are loading:
```bash
python -c "from backend.tools.whisper import get_transcriber; t = get_transcriber(); print('Whisper OK')"
python -c "from backend.tools.diarization import get_diarizer; d = get_diarizer(); print('Diarization OK')"
```

#### Check if LLM service works:
```bash
python -c "from backend.services.llm import get_llm_service; llm = get_llm_service(); print(llm.generate('You are helpful', 'Say hello')); print('LLM OK')"
```

#### Check if pipeline builds:
```bash
python -c "from backend.pipeline.graph import get_pipeline; p = get_pipeline(); print('Pipeline OK')"
```

### What to Share for Help

If you need help debugging, share:

1. **Complete server logs** from the terminal running `python backend/main.py`
2. **The specific NODE where the error occurs** (7, 8, or 11)
3. **Any ❌ error messages** with full traceback
4. **State keys** shown in error messages
5. **Audio file size** from `ls -lh tests/test_consultation.wav`

### Expected Successful Output

When everything works, server logs should show:

```
NODE 7: Clinical Relevance Filter
📝 Input: 16 diarized utterances
🤖 Calling LLM...
✅ LLM generated 2847 characters
✅ Successfully parsed JSON response
✅ Filter complete: 12 included, 4 excluded

NODE 8: Clinical Extractor
📝 Input: 16 filtered utterances
   Included utterances: 12
🤖 Calling LLM...
✅ LLM generated 1523 characters
✅ Successfully parsed JSON response
✅ Extraction complete:
   Symptoms: 2
   Medications: 1
   Vitals: 2

NODE 11: SOAP Generator
📝 Input entities:
   Symptoms: 2
   Medications: 1
   Vitals: 2
🤖 Calling LLM...
✅ LLM generated 1847 characters
✅ Successfully parsed JSON response
✅ SOAP note generated successfully
   Confidence scores:
      Subjective: 0.88
      Objective: 0.92
      Assessment: 0.85
      Plan: 0.90
```

### Quick Fix Checklist

- [ ] Server is running (`python backend/main.py`)
- [ ] `.env` file has valid `GROQ_API_KEY`
- [ ] `.env` file has valid `HF_TOKEN`
- [ ] Test audio file exists and is > 1MB
- [ ] Dependencies are installed (`pip install -r backend/requirements.txt`)
- [ ] HuggingFace model terms accepted
- [ ] Server logs show detailed NODE execution
- [ ] No ❌ errors in server logs

### Still Stuck?

Copy the **complete server logs** (not test client output) and share them. The logs will show exactly where data is being lost.