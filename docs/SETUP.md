# MedScribe Setup Guide

This guide will walk you through setting up MedScribe Phase 1 on your local machine.

---

## Prerequisites

### Required Software

1. **Python 3.11+**
   - Download from: https://www.python.org/downloads/
   - Verify: `python --version`

2. **FFmpeg** (for audio processing)
   - Windows: Download from https://ffmpeg.org/download.html
   - Add to PATH
   - Verify: `ffmpeg -version`

3. **Git** (optional, for cloning)
   - Download from: https://git-scm.com/downloads

### Required API Keys

1. **Groq API Key** (FREE)
   - Sign up at: https://console.groq.com
   - Create API key
   - Free tier includes generous limits

2. **HuggingFace Token** (FREE)
   - Sign up at: https://huggingface.co
   - Go to: https://huggingface.co/settings/tokens
   - Create access token
   - Required for pyannote-audio diarization model

---

## Installation Steps

### Step 1: Clone or Download Project

```bash
# If using Git
git clone https://github.com/yourusername/medscribe.git
cd medscribe

# Or download and extract ZIP
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate

# On macOS/Linux:
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Note**: This will download several large packages:
- faster-whisper (~500MB)
- torch (~2GB)
- pyannote-audio (~1GB)

Installation may take 10-15 minutes depending on your internet speed.

### Step 4: Configure Environment Variables

```bash
# Copy example environment file
cp ../.env.example ../.env

# Edit .env file with your API keys
# On Windows, use: notepad ../.env
# On macOS/Linux, use: nano ../.env
```

**CRITICAL**: Set these values in `.env`:

```env
# Groq API Key (get from https://console.groq.com)
GROQ_API_KEY=your_actual_groq_api_key_here

# HuggingFace Token (get from https://huggingface.co/settings/tokens)
HF_TOKEN=your_actual_huggingface_token_here

# Model Configuration (defaults are fine for Phase 1)
LLM_MODEL=llama-3.1-70b-versatile
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
```

**Common Error**: If you forget to set `HF_TOKEN`, pyannote-audio will fail with:
```
ValueError: HuggingFace token not set!
```

### Step 5: Test Installation

```bash
# Test that Python can import all modules
python -c "import fastapi, groq, faster_whisper, pyannote.audio; print('All imports successful!')"
```

If this succeeds, you're ready to run the server!

---

## Running the Server

### Start the Server

```bash
# Make sure you're in the backend directory
cd backend

# Run the server
python main.py
```

You should see:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Test the Server

Open a new terminal and test:

```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected response:
# {"status":"healthy","service":"MedScribe","version":"0.1.0"}
```

---

## Testing with Sample Audio

### Create a Test Audio File

You need a WAV audio file with a mock doctor-patient conversation.

**Option 1: Record on your phone**
1. Open voice recorder app
2. Record yourself playing both roles:
   - Doctor: "Good morning. What brings you in today?"
   - Patient: "I've been having chest pain for about three days."
   - Doctor: "Can you describe the pain?"
   - Patient: "It's a sharp pain, gets worse when I lie down."
   - Doctor: "Let me check your blood pressure. It's 148 over 92."
   - Doctor: "I'm going to prescribe metformin 500mg twice daily."
3. Save as WAV format
4. Transfer to your computer

**Option 2: Use text-to-speech** (for quick testing)
- Use online TTS tools to generate audio
- Save as WAV

### Test the API

```bash
# Test with your audio file
curl -X POST http://localhost:8000/api/consultation \
  -F "audio_file=@path/to/your/test_audio.wav"
```

**Expected response** (after 20-30 seconds):
```json
{
  "session_id": "uuid-here",
  "status": "completed",
  "message": "SOAP note generated successfully",
  "soap_note": {
    "subjective": {
      "content": "Patient reports chest pain for 3 days...",
      "confidence": 0.92,
      "entities": [...]
    },
    "objective": {...},
    "assessment": {...},
    "plan": {...}
  },
  "processing_time": 28.5
}
```

---

## Troubleshooting

### Issue: "Import groq could not be resolved"

**Solution**: Make sure virtual environment is activated and dependencies are installed:
```bash
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### Issue: "HuggingFace token not set"

**Solution**: 
1. Get token from https://huggingface.co/settings/tokens
2. Add to `.env` file: `HF_TOKEN=your_token_here`
3. Restart server

### Issue: "FFmpeg not found"

**Solution**:
1. Download FFmpeg from https://ffmpeg.org/download.html
2. Add to system PATH
3. Restart terminal
4. Verify: `ffmpeg -version`

### Issue: "CUDA out of memory" or slow processing

**Solution**: Use CPU instead of GPU:
```env
# In .env file
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

### Issue: "Port 8000 already in use"

**Solution**: Change port in `.env`:
```env
API_PORT=8001
```

### Issue: Transcription is inaccurate

**Solution**: Try a larger Whisper model:
```env
# In .env file
WHISPER_MODEL=small  # or medium, or large
```

Note: Larger models are slower but more accurate.

### Issue: Speaker diarization is wrong

**Phase 1 Limitation**: Speaker diarization uses a simplified heuristic (SPEAKER_00 = Doctor, others = Patient). This will be improved in future phases with voice profiles or manual labeling.

**Workaround**: For testing, speak clearly and alternate speakers with pauses.

---

## Development Tips

### Enable Debug Logging

```env
# In .env file
DEBUG=True
```

This will show detailed logs of each pipeline step.

### Test Individual Components

```python
# Test Whisper transcription only
from backend.tools.whisper import get_transcriber
transcriber = get_transcriber()
text = transcriber.transcribe("path/to/audio.wav")
print(text)

# Test diarization only
from backend.tools.diarization import get_diarizer
diarizer = get_diarizer()
result = diarizer.diarize("path/to/audio.wav", "transcript text")
print(result)
```

### Monitor Processing Time

Check logs for timing information:
```
INFO: Transcription complete: 1234 characters
INFO: Diarization complete: 15 utterances
INFO: Filtered 15 utterances: 12 included, 3 excluded
INFO: Extracted 3 symptoms, 2 medications, 2 vitals, 1 lab values
INFO: SOAP note generated successfully
INFO: Consultation abc123 completed in 28.50s
```

---

## Next Steps

Once Phase 1 is working:

1. **Test with real consultations** (with patient consent)
2. **Measure accuracy** of transcription and entity extraction
3. **Collect feedback** from physicians
4. **Prepare for Phase 2**: PaddleOCR integration for test reports

---

## Getting Help

- **Documentation**: See `docs/` folder
- **Architecture**: Read `ARCHITECTURE.md`
- **Workflow**: Read `docs/WORKFLOW.md`
- **Issues**: Check GitHub Issues

---

## System Requirements

### Minimum
- CPU: 4 cores
- RAM: 8GB
- Disk: 10GB free space
- Internet: Required for API calls

### Recommended
- CPU: 8 cores
- RAM: 16GB
- GPU: NVIDIA GPU with 4GB+ VRAM (optional, for faster processing)
- Disk: 20GB free space
- Internet: Stable connection for Groq API

---

## Security Notes

1. **Never commit `.env` file** to version control
2. **Keep API keys secret** - don't share them
3. **Use HTTPS in production** - not HTTP
4. **Validate all inputs** - especially audio files
5. **Sanitize outputs** - before displaying to users

---

You're now ready to use MedScribe Phase 1! 🎉