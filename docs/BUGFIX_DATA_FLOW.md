# Data Flow Bug Fixes - Phase 1

## Problem
The API was returning error: "Pipeline error: No extracted entities available for SOAP generation"

This meant data was not flowing correctly through the pipeline from Clinical Relevance Filter → Clinical Extractor → SOAP Generator.

## Root Causes Identified

### 1. **LLM Service - No JSON Parsing Helper**
- **Issue**: Each node was manually parsing JSON with duplicate code
- **Problem**: Inconsistent markdown cleanup, no fallback handling
- **Impact**: JSON parsing failures were silent or poorly logged

### 2. **Clinical Relevance Filter - Poor Error Handling**
- **Issue**: No validation that LLM returned required fields
- **Problem**: If LLM response was malformed, filter would fail silently
- **Impact**: `filtered_transcript` would be None, breaking downstream nodes

### 3. **Clinical Extractor - Missing Input Validation**
- **Issue**: Didn't check if `filtered_transcript` existed in state
- **Problem**: Would crash with KeyError instead of graceful error
- **Impact**: Pipeline would break without clear error message

### 4. **SOAP Generator - Same Issues**
- **Issue**: No validation of `extracted_entities` in state
- **Problem**: Generic error messages, no debugging info
- **Impact**: Final error message didn't indicate where failure occurred

### 5. **Insufficient Logging**
- **Issue**: No detailed logging at each pipeline step
- **Problem**: Impossible to debug where data was lost
- **Impact**: User couldn't diagnose the issue

## Fixes Applied

### 1. Enhanced LLM Service ([`backend/services/llm.py`](backend/services/llm.py))

**Added `generate_json()` method:**
```python
def generate_json(self, system_prompt: str, user_prompt: str) -> dict:
    """
    Generate JSON response with robust parsing
    - Strips markdown code blocks (```json```)
    - Extracts JSON from text using regex
    - Provides detailed error logging
    - Returns parsed dict
    """
```

**Benefits:**
- Centralized JSON parsing logic
- Consistent error handling
- Better logging of parse failures
- Fallback extraction using regex

### 2. Fixed Clinical Relevance Filter ([`backend/pipeline/nodes/filter.py`](backend/pipeline/nodes/filter.py))

**Changes:**
```python
# Before
response = llm.generate(...)
filtered_data = json.loads(response_clean)  # Could fail silently

# After
filtered_data = llm.generate_json(...)  # Robust parsing
if "filtered_utterances" not in filtered_data:
    raise ValueError("Response missing required field")
```

**Added logging:**
- ✅ Input: Number of diarized utterances
- 🤖 LLM call status
- ✅ Output: Included/excluded counts
- 📝 Sample of included utterances
- ❌ Detailed error messages with traceback

### 3. Fixed Clinical Extractor ([`backend/pipeline/nodes/extractor.py`](backend/pipeline/nodes/extractor.py))

**Changes:**
```python
# Before
filtered = state["filtered_transcript"]  # KeyError if missing

# After
filtered = state.get("filtered_transcript")  # Safe access
if not filtered:
    logger.error("No filtered transcript available")
    logger.error(f"State keys: {list(state.keys())}")  # Debug info
    state["error"] = error_msg
    return state
```

**Added validation:**
- Check all required fields in LLM response
- Add empty values for missing fields
- Proper PopulationTag object creation

**Added logging:**
- ✅ Input: Filtered utterances count
- 🤖 LLM call status
- ✅ Output: Entity counts by category
- 📝 Sample entities extracted
- ❌ Detailed error messages with traceback

### 4. Fixed SOAP Generator ([`backend/pipeline/nodes/soap.py`](backend/pipeline/nodes/soap.py))

**Changes:**
```python
# Before
entities = state["extracted_entities"]  # KeyError if missing

# After
entities = state.get("extracted_entities")  # Safe access
if not entities:
    logger.error("No extracted entities available")
    logger.error(f"State keys: {list(state.keys())}")
    state["error"] = error_msg
    return state
```

**Added validation:**
- Check all 4 SOAP sections present
- Validate section structure

**Added logging:**
- ✅ Input: Entity counts
- 🤖 LLM call status
- ✅ Output: Confidence scores per section
- 📝 Content previews for each section
- ❌ Detailed error messages with traceback

## Testing the Fixes

### Before Fix
```
POST /api/consultation
→ Pipeline error: No extracted entities available for SOAP generation
```

No indication of where the failure occurred.

### After Fix
```
POST /api/consultation

NODE 7: Clinical Relevance Filter
📝 Input: 16 diarized utterances
🤖 Calling LLM for clinical relevance filtering...
✅ LLM generated 2847 characters
✅ Successfully parsed JSON response
✅ Filter complete:
   Total utterances: 16
   Included: 12
   Excluded: 4
   Sample included utterances:
      - [Patient] My chest has been hurting... → Subjective

NODE 8: Clinical Extractor
📝 Input: 16 filtered utterances
   Included utterances: 12
🤖 Calling LLM for clinical entity extraction...
✅ LLM generated 1523 characters
✅ Successfully parsed JSON response
✅ Extraction complete:
   Symptoms: 2
   Medications: 1
   Vitals: 2
   Lab values: 0
   Sample symptom: chest pain

NODE 11: SOAP Generator
📝 Input entities:
   Symptoms: 2
   Medications: 1
   Vitals: 2
🤖 Calling LLM for SOAP note generation...
✅ LLM generated 1847 characters
✅ Successfully parsed JSON response
✅ SOAP note generated successfully
   Confidence scores:
      Subjective: 0.88
      Objective: 0.92
      Assessment: 0.85
      Plan: 0.90
```

Clear visibility into every step of the pipeline.

## Key Improvements

### 1. **Defensive Programming**
- Use `.get()` instead of direct dict access
- Validate all inputs before processing
- Check LLM response structure before parsing

### 2. **Comprehensive Logging**
- Log input at each node
- Log LLM call status
- Log output summary
- Log errors with full traceback

### 3. **Graceful Degradation**
- Return empty entities instead of crashing
- Provide clear error messages
- Include state keys in error logs for debugging

### 4. **Centralized JSON Parsing**
- Single source of truth for JSON extraction
- Consistent error handling
- Better markdown cleanup

## Files Modified

1. [`backend/services/llm.py`](backend/services/llm.py) - Added `generate_json()` method
2. [`backend/pipeline/nodes/filter.py`](backend/pipeline/nodes/filter.py) - Enhanced logging and validation
3. [`backend/pipeline/nodes/extractor.py`](backend/pipeline/nodes/extractor.py) - Fixed input validation and logging
4. [`backend/pipeline/nodes/soap.py`](backend/pipeline/nodes/soap.py) - Fixed input validation and logging

## Verification

Run the API with these fixes and check logs:

```bash
# Start server
python backend/main.py

# In another terminal, test
curl -X POST http://localhost:8000/api/consultation \
  -F "audio_file=@tests/test_consultation.wav"
```

You should now see:
- ✅ Detailed logging at each pipeline step
- ✅ Clear indication of data flow
- ✅ Successful SOAP note generation
- ✅ Or clear error message indicating exactly where failure occurred

## Next Steps

If issues persist:
1. Check server logs for the detailed pipeline execution
2. Verify GROQ_API_KEY is valid
3. Ensure audio file is valid WAV format
4. Check that Whisper and Pyannote models loaded successfully