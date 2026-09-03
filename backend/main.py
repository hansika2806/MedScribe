import logging
import os
import asyncio
from pathlib import Path

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def setup_ffmpeg():
    import platform
    import shutil

    # On Linux (Railway/Docker), ffmpeg is installed via nixpacks/apt and already on PATH
    if platform.system() != "Windows":
        if shutil.which("ffmpeg"):
            logger.info("FFmpeg found on PATH (Linux/Docker environment)")
        else:
            logger.warning("FFmpeg not found on PATH. Audio processing may fail.")
        return

    # Windows local dev: try the WinGet install location
    ffmpeg_path = (
        Path(os.environ.get("USERPROFILE", "C:/Users/nagah"))
        / "AppData/Local/Microsoft/WinGet/Packages"
        / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
        / "ffmpeg-8.1.1-full_build/bin"
    )

    try:
        ffmpeg_exists = ffmpeg_path.exists()
    except PermissionError:
        ffmpeg_exists = False
        logger.warning("Cannot inspect default FFmpeg path due to permissions.")

    if ffmpeg_exists:
        current_path = os.environ.get("PATH", "")
        if str(ffmpeg_path) not in current_path:
            os.environ["PATH"] = str(ffmpeg_path) + os.pathsep + current_path
            logger.info(f"FFmpeg added to PATH: {ffmpeg_path}")
    else:
        logger.warning(
            "FFmpeg not found at default WinGet location. Audio processing may fail."
        )


setup_ffmpeg()

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from backend.api.routes import router
from backend.auth.router import router as auth_router
from backend.config import get_settings
from backend.database import init_db

settings = get_settings()


async def warm_models():
    """Warm heavy local models after the API starts accepting requests."""
    try:
        from backend.tools.whisper import get_transcriber

        await run_in_threadpool(get_transcriber)
        logger.info("Whisper model pre-loaded")
    except Exception as e:
        logger.warning(f"Whisper pre-load failed: {e}", exc_info=True)

    try:
        from backend.tools.corpus_loader import load_corpus

        await run_in_threadpool(load_corpus)
        logger.info("RAG corpus pre-loaded")
    except Exception as e:
        logger.warning(f"RAG corpus pre-load failed: {e}", exc_info=True)

    hf_token = os.getenv("HF_TOKEN")
    if hf_token:
        try:
            from backend.tools.diarization import get_pyannote_diarizer

            await run_in_threadpool(get_pyannote_diarizer)
            logger.info("Diarization model pre-loaded")
        except Exception as e:
            logger.warning(f"Diarization pre-load failed: {e}", exc_info=True)

    logger.info("All models pre-loaded. Ready.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    init_db()
    logger.info("SQLite database initialized")
    
    # Start model warming in background
    asyncio.create_task(warm_models())
    
    # Start periodic cleanup task
    cleanup_task = asyncio.create_task(periodic_cleanup())
    
    yield
    
    # Shutdown
    logger.info("Shutting down MedScribe API")
    
    # Cancel cleanup task
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    
    # Final cleanup
    from backend.cleanup import cleanup_temp_files
    deleted, errors = cleanup_temp_files(max_age_hours=0)  # Clean all files on shutdown
    logger.info(f"Shutdown cleanup: {deleted} files deleted, {errors} errors")


async def periodic_cleanup():
    """Run cleanup tasks periodically."""
    from backend.cleanup import cleanup_temp_files, monitor_temp_directory
    
    while True:
        try:
            # Wait 1 hour between cleanups
            await asyncio.sleep(3600)
            
            # Monitor temp directory
            monitor_temp_directory(warn_size_mb=1000)
            
            # Clean up old files (older than 24 hours)
            deleted, errors = cleanup_temp_files(max_age_hours=24)
            if deleted > 0 or errors > 0:
                logger.info(f"Periodic cleanup: {deleted} files deleted, {errors} errors")
                
        except asyncio.CancelledError:
            logger.info("Periodic cleanup task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in periodic cleanup: {e}", exc_info=True)
            # Continue running despite errors


app = FastAPI(
    title="MedScribe API",
    description="Clinical Documentation AI - Demo Ready",
    version="1.0.0-demo",
    debug=settings.debug,
    lifespan=lifespan
)

# CORS middleware - configurable origins + local dev regex
cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://[a-zA-Z0-9\-]+\.vercel\.app|https://[a-zA-Z0-9\-]+\.railway\.app|http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*", "Authorization"],
)

# Include routes with API versioning
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(router, prefix="/api/v1", tags=["Consultations"])

# Backward compatibility routes (deprecated)
app.include_router(auth_router, prefix="/auth", tags=["Authentication (Deprecated)"])
app.include_router(router, tags=["Consultations (Deprecated)"])


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "MedScribe API - Clinical Documentation AI",
        "version": "1.0.0-demo",
        "status": "running",
        "phase": "Phase 7 Demo Ready",
        "features": [
            "Audio transcription (faster-whisper)",
            "Real speaker diarization (pyannote + Speechbrain + fallback)",
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
            "JWT physician authentication",
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
