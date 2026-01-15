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

    # Load models (optional - can be loaded lazily on first request)
    whisperx = get_whisperx_service()
    diarization = get_diarization_service()

    try:
        whisperx.load_model()
        logger.info("WhisperX model loaded")
    except Exception as e:
        logger.warning(f"WhisperX model not loaded on startup: {e}")

    try:
        diarization.load_pipeline()
        logger.info("Diarization pipeline loaded")
    except Exception as e:
        logger.warning(f"Diarization pipeline not loaded on startup: {e}")

    logger.info("Transcriptor API started")
    yield
    # Shutdown
    logger.info("Shutting down Transcriptor API...")


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


# Serve static files
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/")
    async def serve_index():
        """Serve the frontend index.html."""
        return FileResponse(str(static_dir / "index.html"))
