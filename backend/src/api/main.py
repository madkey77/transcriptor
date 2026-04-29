import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

from src.storage.database import create_tables
from src.api.middleware import setup_middleware, setup_exception_handlers
from src.api.routes import transcribe, history
from src.transcription.whisperx_service import get_whisperx_service
from src.transcription.diarization import get_diarization_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Transcriptor API...")
    create_tables()

    # Mark any orphan jobs (left as pending/processing from a previous run) as failed.
    from src.storage.database import get_db_context
    from src.storage.repository import TranscriptionRepository
    from src.storage.models import Transcription, TranscriptionStatus
    with get_db_context() as db:
        orphans = (
            db.query(Transcription)
            .filter(Transcription.status.in_([
                TranscriptionStatus.PENDING,
                TranscriptionStatus.PROCESSING,
            ]))
            .all()
        )
        for o in orphans:
            o.status = TranscriptionStatus.FAILED
            o.error_message = "Interrupted by restart"
        if orphans:
            db.commit()
            logger.info(f"Marked {len(orphans)} orphan jobs as failed")

    # Load models — fail fast if CUDA isn't there.
    whisperx = get_whisperx_service()
    diarization = get_diarization_service()
    whisperx.load_model()
    logger.info("WhisperX model loaded")
    try:
        diarization.load_pipeline()
        logger.info("Diarization pipeline loaded")
    except Exception as e:
        logger.warning(f"Diarization not available: {e}")

    # Start the transcription queue worker.
    from src.transcription.queue import get_queue
    from src.transcription.queue_handler import queue_job_handler
    queue = get_queue()
    await queue.start_worker(queue_job_handler)
    logger.info("Transcription queue worker started")

    logger.info("Transcriptor API started")
    yield
    # Shutdown
    logger.info("Shutting down Transcriptor API...")
    await queue.stop_worker()
    logger.info("Queue worker stopped")


app = FastAPI(
    title="Transcriptor API",
    description="Audio transcription service with speaker diarization for Brazilian Portuguese",
    version="1.0.0",
    lifespan=lifespan
)

# Setup middleware and exception handlers
setup_middleware(app)
setup_exception_handlers(app)

# Register routes
app.include_router(transcribe.router)
app.include_router(history.router)


@app.get("/api/health")
async def health_check():
    """Check if the API is running and models are loaded."""
    whisperx = get_whisperx_service()
    diarization = get_diarization_service()

    return {
        "status": "healthy",
        "whisper_model_loaded": whisperx.is_loaded(),
        "diarization_available": diarization.is_available()
    }


# Serve the built React frontend.
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    assets_dir = static_dir / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Mount the rest of /static for ad-hoc files (favicon, etc.).
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(str(static_dir / "index.html"))

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        # API routes are registered above and take precedence. Anything else
        # that doesn't map to a file falls back to the SPA's index.html.
        candidate = static_dir / full_path
        if candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(static_dir / "index.html"))
