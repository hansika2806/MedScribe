from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from backend.config import get_settings
from backend.database import init_db
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
settings = get_settings()

app = FastAPI(
    title="MedScribe API",
    description="Clinical Documentation AI - Phase 4",
    version="0.4.0-phase4",
    debug=settings.debug
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes WITHOUT prefix for backward compatibility
app.include_router(router)


@app.on_event("startup")
async def startup_event():
    """Initialize SQLite persistence on startup."""
    init_db()
    logger.info("SQLite database initialized")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "MedScribe API - Clinical Documentation AI",
        "version": "0.4.0-phase4",
        "status": "running",
        "phase": "Phase 4",
        "features": [
            "Audio transcription (faster-whisper)",
            "Real speaker diarization (Speechbrain + fallback)",
            "Clinical relevance filtering",
            "Entity extraction with provenance",
            "RAG with clinical guidelines (30+ sources)",
            "ICD-10 coding (NLM API)",
            "QA guardrails (5 failure modes)",
            "Safety guardrails (drug interactions, red flags)",
            "Intelligent routing (urgent/review/standard)",
            "SOAP note generation with citations",
            "Comprehensive metrics tracking",
            "SQLite persistence",
            "Physician review and approval workflow",
            "PDF lab report OCR upload",
            "Structured per-node performance logging",
        ]
    }


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting MedScribe API on {settings.api_host}:{settings.api_port}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"LLM Model: {settings.llm_model}")
    logger.info(f"Whisper Model: {settings.whisper_model}")

    backend_dir = Path(__file__).resolve().parent
    
    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
        # Only watch backend source files so temp uploads, Chroma writes,
        # and generated test artifacts do not trigger mid-request reloads.
        reload_dirs=[str(backend_dir)],
        reload_excludes=[
            "data/*",
            "tests/*",
            "docs/*",
            "venv/*",
            "*.md",
        ],
    )

# Made with Bob
